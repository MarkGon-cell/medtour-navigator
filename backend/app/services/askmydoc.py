"""
Client for https://api.askmydoc.in — free, key-less NMC IMR verification.

Caching layers (three, from fastest to most durable):

1. In-memory TTL cache (module-level dict) — identical lookups inside the
   TTL window return instantly without a network round trip. Bounded so a
   long-lived worker cannot grow it without limit.
2. `doctors.verification_json` / `verified_at` on the row — written once at
   register (or explicit re-verify) so `/doctor/auth/me` is always local.
3. askmydoc's own upstream cache (`cache_size` in /api/health) — we inherit
   it anyway; our TTL just keeps the backend from being the requester.

The upstream payload shape is defensive: the API returns 90+ IMR fields and
may return `{"error": ...}` with HTTP 200 for an unverifiable number, so we
normalize instead of assuming keys.
"""

import json
import threading
import time
from typing import Any, Optional

import httpx

ASKMYDOC_BASE = "https://api.askmydoc.in"

# Debounce window: one network call per (reg_number, council, year) per hour.
CACHE_TTL_SECONDS = 3600
# Cap the in-memory cache so it cannot grow without bound.
CACHE_MAX_ENTRIES = 512

# key -> (monotonic timestamp, normalized result dict)
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()

# External API failures must not take the portal down: a doctor whose cached
# verification exists keeps working; only a first-time register with the API
# down sees the error.
HTTP_TIMEOUT_SECONDS = 8.0


def _cache_key(reg_number: str, state_council: Optional[str], year: Optional[str]) -> str:
    return f"{reg_number.strip().lower()}|{(state_council or '').strip().lower()}|{(year or '').strip()}"


def _cache_get(key: str) -> Optional[dict]:
    with _cache_lock:
        entry = _cache.get(key)
        if not entry:
            return None
        stored_at, value = entry
        if time.monotonic() - stored_at > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        return dict(value, cached=True)


def _cache_put(key: str, value: dict) -> None:
    with _cache_lock:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            # Drop the oldest half (insertion order in dicts is stable enough
            # for a debounce cache — correctness does not depend on which go).
            for stale_key in list(_cache.keys())[: CACHE_MAX_ENTRIES // 2]:
                _cache.pop(stale_key, None)
        _cache[key] = (time.monotonic(), dict(value, cached=False))


def _normalize(raw: Any, http_ok: bool, reg_number: str) -> dict:
    """
    Fold whatever the upstream returned into a stable shape:

      { verified: bool, cached: bool, name, reg_number, state_council,
        year, qualification, status, reason, raw, fetched_at }
    """
    fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _failure(status: str, reason: str, payload: Any) -> dict:
        return {
            "verified": False,
            "cached": False,
            "name": None,
            "reg_number": reg_number,
            "state_council": None,
            "year": None,
            "qualification": None,
            "status": status,
            "reason": reason,
            "raw": payload if isinstance(payload, (dict, list)) else None,
            "fetched_at": fetched_at,
        }

    if not http_ok or not isinstance(raw, dict):
        return _failure(
            "unavailable",
            "Verification service is unavailable right now. Please try again shortly.",
            raw,
        )

    if raw.get("error") or raw.get("success") is False:
        # The service answered, but WHAT it answered with matters:
        #   - "Portal returned HTTP 404" / "HTTP 503" / "unreachable" means
        #     THEIR NMC portal fetch failed -> the service is degraded, and we
        #     must NOT tell the caller "this doctor does not exist".
        #   - Only a clean negative (no record found) is a definitive not_found.
        error_text = str(raw.get("error") or raw.get("message") or "")
        lowered = error_text.lower()
        service_broke = any(
            marker in lowered
            for marker in (
                "portal returned",
                "http 5",
                "http 4",
                "unreachable",
                "timeout",
                "non-json",
                "bad gateway",
                "unavailable",
            )
        )
        if service_broke:
            return _failure(
                "unavailable",
                "Verification service could not reach the NMC register. Please try again shortly.",
                raw,
            )
        return _failure(
            "not_found",
            error_text or "No IMR record found for this registration number.",
            raw,
        )

    # Defensive field extraction — IMR payloads name things inconsistently.
    def _first(*keys: str) -> Optional[str]:
        for k in keys:
            val = raw.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, (int, float)):
                return str(val)
        return None

    name = _first("name", "doctor_name", "full_name", "registered_name")
    status = _first("status", "verification_status", "registration_status")
    found = bool(raw.get("verified")) or bool(raw.get("match")) or bool(name) or (status or "").lower() in (
        "verified",
        "active",
        "found",
        "valid",
    )

    return {
        "verified": bool(found),
        "cached": False,
        "name": name,
        "reg_number": _first("reg_number", "registration_number", "registration_no") or reg_number,
        "state_council": _first("state_council", "council", "council_name", "state"),
        "year": _first("year", "reg_year", "registration_year", "year_of_registration"),
        "qualification": _first("qualification", "qualifications", "degree", "degrees"),
        "status": status or ("verified" if found else "unknown"),
        "reason": None if found else "Registration number could not be matched in the NMC register.",
        "raw": raw,
        "fetched_at": fetched_at,
    }


def verify_doctor(
    reg_number: str,
    state_council: Optional[str] = None,
    year: Optional[str] = None,
    force_refresh: bool = False,
) -> dict:
    """
    Verify a doctor's NMC registration number against the IMR via
    api.askmydoc.in. Synchronous (FastAPI runs this in the threadpool);
    returns the normalized dict described in `_normalize`.
    """
    key = _cache_key(reg_number, state_council, year)

    if not force_refresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    params: dict[str, str] = {"reg_number": reg_number.strip()}
    if state_council and state_council.strip():
        params["state_council"] = state_council.strip()
    if year and str(year).strip():
        params["year"] = str(year).strip()

    http_ok = False
    raw: Any = None
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(f"{ASKMYDOC_BASE}/api/verify", params=params)
            http_ok = resp.status_code == 200
            try:
                raw = resp.json()
            except ValueError:
                raw = {"error": f"HTTP {resp.status_code} (non-JSON response)"}
    except httpx.HTTPError as exc:
        raw = {"error": f"Verification service unreachable: {exc.__class__.__name__}"}

    result = _normalize(raw, http_ok, reg_number)
    # Only cache DECISIVE answers. A degraded/unavailable service must be
    # retried on the next attempt instead of poisoning the cache for an hour.
    if result["verified"] or result["status"] == "not_found":
        _cache_put(key, result)
    return result


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def cache_stats() -> dict:
    with _cache_lock:
        return {
            "entries": len(_cache),
            "ttl_seconds": CACHE_TTL_SECONDS,
            "max_entries": CACHE_MAX_ENTRIES,
        }
