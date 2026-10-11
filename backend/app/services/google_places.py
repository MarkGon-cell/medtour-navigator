"""
Google Places rating enrichment, quota-safe for a demo / trial key.

Why this exists
---------------
The national hospital directory carries no user ratings or reviews. This
module pulls the *real* rating and review count for hospitals from the
Google Places API (New) so `infer_reputation` can prefer a sourced rating
over its name/services inference.

The caller is usually on a Google Maps **demo / free-trial key**, so every
request counts against a tiny quota. This module is therefore built to burn
as little of it as possible, and to keep working when the key cannot be used
at all (a plain docs "demo" key is typically restricted to Google's own
domains and will be rejected -- see _circuit below).

Rate-limiting / quota controls
------------------------------
1. ONE Nearby Search per *area*, not per hospital. A single call returns up
   to `MAX_PLACES` nearby places; we then match them to our candidates by
   name. So enriching 10 hospitals costs 1 API request, not 10.
2. Token bucket -- at most `RATE_PER_MINUTE` lookups per rolling minute.
3. Daily budget -- at most `DAILY_BUDGET` lookups per process lifetime, so a
   burst of requests cannot empty the quota and then start failing loudly.
4. Area cache with a long TTL -- ratings change slowly, so the same
   neighbourhood is looked up at most once per `CACHE_TTL_S`.
5. Circuit breaker -- after `CIRCUIT_FAILURES` consecutive failures (bad key,
   no billing, quota exhausted, network down) the provider disables itself
   for `CIRCUIT_COOLDOWN_S`. A demo key that will never work therefore costs
   a couple of rejected calls, not one per request.

Everything degrades to "no rating" on failure -- the caller falls back to
inferred reputation. This module must never raise into a request.
"""

import logging
import os
import re
import threading
import time
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Accept either name: GOOGLE_PLACES_API_KEY is the canonical one; a key stored
# as GOOGLE_MAPS_DEMO_API_KEY (the common label on a sample/demo key) is used
# as a fallback so the caller does not have to rename it.
GOOGLE_PLACES_API_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_DEMO_API_KEY")
)
NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Only ask for the fields we use -- every extra field is billed weight.
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.rating",
    "places.userRatingCount",
    "places.formattedAddress",
])

# --- Tunables (override via env) -------------------------------------------
RATE_PER_MINUTE = int(os.getenv("GOOGLE_PLACES_RATE_PER_MINUTE", "6"))
DAILY_BUDGET = int(os.getenv("GOOGLE_PLACES_DAILY_BUDGET", "300"))
MAX_PLACES = int(os.getenv("GOOGLE_PLACES_MAX_PLACES", "20"))
CACHE_TTL_S = 7 * 24 * 3600          # ratings barely move; cache for a week
CIRCUIT_FAILURES = 3                 # consecutive failures before cooldown
CIRCUIT_COOLDOWN_S = 15 * 60         # how long the breaker stays open
PER_CALL_TIMEOUT_S = 6.0             # keep the triage path responsive

# --- Module state (process-local; reset on restart, which is fine) ---------
_lock = threading.Lock()
_bucket_times: list[float] = []      # timestamps of recent lookups (token bucket)
_daily_count = 0
_daily_reset_at = 0.0
_cache: Dict[tuple, tuple[float, Dict[str, dict]]] = {}
_consecutive_failures = 0
_circuit_open_until = 0.0
_disabled_reason: Optional[str] = None   # set when the key is unusable


# -------------------------------------------------------------------------
# Name normalisation for candidate <-> Places matching
# -------------------------------------------------------------------------
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm_name(name: Optional[str]) -> str:
    return _NON_ALNUM.sub(" ", (name or "").lower()).strip()


def _names_match(a: Optional[str], b: Optional[str]) -> bool:
    """Loose match so 'Apollo Hospital' lines up with 'Apollo Hospitals, Bandra'."""
    na, nb = _norm_name(a), _norm_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return False
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.6


# -------------------------------------------------------------------------
# Rate limiter: token bucket + daily budget + circuit breaker
# -------------------------------------------------------------------------
def _allow_lookup() -> tuple[bool, str]:
    """Return (allowed, reason_if_not)."""
    global _daily_count, _daily_reset_at

    if not GOOGLE_PLACES_API_KEY:
        return False, "no_api_key"

    now = time.time()

    with _lock:
        # Circuit breaker open?
        if now < _circuit_open_until:
            return False, "circuit_open"

        # Daily budget: reset at UTC midnight.
        if now >= _daily_reset_at:
            _daily_count = 0
            _daily_reset_at = _start_of_next_utc_day(now)
        if _daily_count >= DAILY_BUDGET:
            return False, "daily_budget_exhausted"

        # Token bucket: drop timestamps older than 60s, then check the cap.
        cutoff = now - 60.0
        while _bucket_times and _bucket_times[0] < cutoff:
            _bucket_times.pop(0)
        if len(_bucket_times) >= RATE_PER_MINUTE:
            return False, "rate_limited"

        # Reserve the slot now so concurrent threads cannot over-fill.
        _bucket_times.append(now)
        _daily_count += 1

    return True, "ok"


def _start_of_next_utc_day(now: float) -> float:
    # Seconds until next UTC midnight, added to now.
    tm = time.gmtime(now)
    seconds_since_midnight = tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec
    return now + (86400 - seconds_since_midnight)


def _record_success() -> None:
    global _consecutive_failures
    with _lock:
        _consecutive_failures = 0


def _record_failure(open_circuit: bool = True) -> None:
    """Count a failure; open the breaker when too many stack up."""
    global _consecutive_failures, _circuit_open_until
    with _lock:
        _consecutive_failures += 1
        if open_circuit and _consecutive_failures >= CIRCUIT_FAILURES:
            _circuit_open_until = time.time() + CIRCUIT_COOLDOWN_S
            logger.warning(
                "Google Places circuit open for %ds after %d failures",
                CIRCUIT_COOLDOWN_S, _consecutive_failures,
            )


def _disable_permanently(reason: str) -> None:
    """Key is unusable (e.g. demo/restricted/no billing): stop trying."""
    global _disabled_reason
    with _lock:
        if _disabled_reason is None:
            _disabled_reason = reason
            logger.info("Google Places disabled: %s", reason)


# -------------------------------------------------------------------------
# Provider call
# -------------------------------------------------------------------------
def _search_nearby(latitude: float, longitude: float, radius_km: float) -> Dict[str, dict]:
    """
    One Nearby Search for the whole area.

    Returns a map: normalised place name -> {"rating", "review_count"}.
    Raises on transport/auth errors so the caller can drive the breaker.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    payload = {
        # Only types Places API (New) accepts. "clinic" is NOT valid and makes
        # the whole request 400, which would silently disable ratings; "doctor"
        # covers clinics/GP practices. (Verified against the live API.)
        "includedTypes": ["hospital", "doctor"],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                # API caps radius at 50000 m.
                "radius": min(radius_km, 50.0) * 1000.0,
            }
        },
        "maxResultCount": min(MAX_PLACES, 20),
    }

    resp = requests.post(NEARBY_URL, headers=headers, json=payload, timeout=PER_CALL_TIMEOUT_S)

    if resp.status_code in (401, 403):
        # Auth problem -- a restricted "demo" key lands here. Permanent.
        raise PermissionError(f"places_auth_{resp.status_code}")
    resp.raise_for_status()

    data = resp.json()
    out: Dict[str, dict] = {}
    for place in data.get("places", []):
        name = (place.get("displayName") or {}).get("text")
        rating = place.get("rating")
        reviews = place.get("userRatingCount")
        if name and isinstance(rating, (int, float)):
            out[_norm_name(name)] = {
                "rating": float(rating),
                "review_count": int(reviews) if isinstance(reviews, (int, float)) else None,
            }
    return out


# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------
def fetch_ratings_map(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> Dict[str, dict]:
    """
    Return {normalised_name: {"rating", "review_count"}} for the area.

    Rate-limited, cached, circuit-broken. Never raises; returns {} whenever
    the provider is disabled, limited, failing, or simply has no data -- the
    caller keeps inferred reputation in that case.
    """
    global _disabled_reason

    if _disabled_reason:
        return {}

    key = (round(latitude, 2), round(longitude, 2), round(radius_km, 1))

    # Cache first -- a hit costs nothing against the quota.
    with _lock:
        entry = _cache.get(key)
    if entry:
        stamp, value = entry
        if time.time() - stamp < CACHE_TTL_S:
            return value

    allowed, reason = _allow_lookup()
    if not allowed:
        if reason == "no_api_key":
            _disable_permanently("no_api_key")
        elif reason == "daily_budget_exhausted":
            logger.info("Google Places daily budget exhausted; using inference")
        else:
            logger.info("Google Places lookup skipped: %s", reason)
        return {}

    try:
        ratings = _search_nearby(latitude, longitude, radius_km)
    except PermissionError as exc:
        # Demo / restricted / billing-less key: stop trying for good.
        _disable_permanently(str(exc))
        return {}
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
        _record_failure()
        logger.info("Google Places lookup failed: %s: %s", type(exc).__name__, exc)
        return {}
    else:
        _record_success()
        with _lock:
            _cache[key] = (time.time(), ratings)
        return ratings


def enrich_candidates_with_ratings(
    candidates: list,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> int:
    """
    Attach a real Google rating/review_count to each candidate by name match.

    Mutates the candidate dicts in place (sets "rating" and "review_count"
    only when a match is found; never overwrites with None). Returns the
    number of candidates enriched. Never raises.
    """
    if not candidates:
        return 0

    try:
        ratings = fetch_ratings_map(latitude, longitude, radius_km)
    except Exception:  # noqa: BLE001
        return 0
    if not ratings:
        return 0

    enriched = 0
    for c in candidates:
        cname = _norm_name(c.get("name"))
        if not cname:
            continue
        # Exact normalised match first, then loose containment.
        hit = ratings.get(cname)
        if hit is None:
            for norm_name, value in ratings.items():
                if _names_match(cname, norm_name):
                    hit = value
                    break
        if hit:
            c["rating"] = hit.get("rating")
            c["review_count"] = hit.get("review_count")
            enriched += 1

    return enriched


def provider_status() -> dict:
    """Introspection for /health or debugging."""
    with _lock:
        return {
            "configured": bool(GOOGLE_PLACES_API_KEY),
            "disabled_reason": _disabled_reason,
            "circuit_open": time.time() < _circuit_open_until,
            "daily_used": _daily_count,
            "daily_budget": DAILY_BUDGET,
            "rate_per_minute": RATE_PER_MINUTE,
            "cached_areas": len(_cache),
        }
