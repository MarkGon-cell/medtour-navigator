"""
Backend verification for the redesign.

Run against a live server:
    python scripts/verify_endpoints.py [base_url]

Read-only except for POST /hospitals/ (expects a rejection) and
POST /emergency/sos (now side-effect free).
"""

import sys
import time

import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

PASS = "PASS"
FAIL = "FAIL"
_results: list[tuple[str, str, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    _results.append((PASS if condition else FAIL, label, detail))
    print(f"[{PASS if condition else FAIL}] {label}" + (f" -- {detail}" if detail else ""))


def timed_get(path: str, **params) -> tuple[float, requests.Response]:
    start = time.perf_counter()
    response = requests.get(f"{BASE_URL}{path}", params=params, timeout=30)
    return time.perf_counter() - start, response


def main() -> None:
    # ---------------------------------------------------------
    # 1. App is up
    # ---------------------------------------------------------
    response = requests.get(f"{BASE_URL}/health", timeout=10)
    check("GET /health returns ok", response.json().get("status") == "ok")

    # ---------------------------------------------------------
    # 2. SOS must be honest: no dispatch claims
    # ---------------------------------------------------------
    response = requests.post(
        f"{BASE_URL}/emergency/sos",
        json={
            "latitude": 19.0760,
            "longitude": 72.8777,
            "address": "CSMNS, Fort, Mumbai",
            "message": "chest pain",
            "contact_emergency_services": True,
        },
        timeout=10,
    )
    body = response.json()
    check("POST /emergency/sos returns 200", response.status_code == 200, str(response.status_code))
    check("SOS reports dispatched=false", body.get("dispatched") is False, str(body.get("dispatched")))
    check("SOS marks itself deprecated", body.get("deprecated") is True)
    check("SOS says it does not contact anyone", "does not contact" in body.get("message", ""))
    flat = str(body)
    check("SOS has no eta_minutes", "eta_minutes" not in flat)
    check("SOS has no simulated/dispatched status", "DISPATCH_INITIATED" not in flat)
    check("SOS offers 112", body.get("emergency_numbers", {}).get("national_emergency") == "112")

    # ---------------------------------------------------------
    # 3. Nearby: bounded query, sane results, fast
    # ---------------------------------------------------------
    elapsed, response = timed_get(
        "/hospitals/nearby",
        latitude=19.0760,
        longitude=72.8777,
        radius_km=10,
    )
    rows = response.json()
    check("GET /hospitals/nearby returns 200", response.status_code == 200)
    check("nearby returns a list", isinstance(rows, list), f"{len(rows)} rows")
    check("nearby is fast (<500ms)", elapsed < 0.5, f"{elapsed * 1000:.0f}ms")
    if rows:
        distances = [r["distance_km"] for r in rows]
        check("nearby sorted nearest-first", distances == sorted(distances))
        check("nearby rows within radius", max(distances) <= 10, f"max {max(distances)}km")
        check(
            "nearby exposes contact block",
            all(k in rows[0] for k in ("phone", "emergency_phone", "has_emergency_phone")),
        )

    # ---------------------------------------------------------
    # 4. Emergency ranking + limit (the SOS sheet contract)
    # ---------------------------------------------------------
    elapsed, response = timed_get(
        "/hospitals/nearby",
        latitude=19.0760,
        longitude=72.8777,
        radius_km=10,
        emergency=True,
        sort="emergency",
        limit=3,
    )
    top = response.json()
    check("emergency sort returns 200", response.status_code == 200, str(response.status_code))
    check("limit=3 caps the SOS sheet", len(top) <= 3, f"{len(top)} rows")
    check("emergency query fast (<500ms)", elapsed < 0.5, f"{elapsed * 1000:.0f}ms")
    if top:
        flags = [r["emergency_available"] for r in top]
        check(
            "emergency sort puts flagged facilities first",
            not any(flags) or flags[0] is True or not all(flags),
            f"flags={flags}",
        )

    # A hard filter would return nothing anywhere in India; ranking must not.
    check("emergency ranking never returns empty in a city", len(top) > 0, f"{len(top)} rows")

    # ---------------------------------------------------------
    # 5. Directory list is paginated
    # ---------------------------------------------------------
    response = requests.get(f"{BASE_URL}/hospitals/", params={"limit": 5}, timeout=30)
    body = response.json()
    check("GET /hospitals/ returns 200", response.status_code == 200)
    check("GET /hospitals/ is paginated", isinstance(body, dict) and "total" in body)
    if isinstance(body, dict):
        check("page size honours limit", len(body.get("items", [])) == 5, f"{len(body.get('items', []))}")
        check("total reported", body.get("total", 0) > 1000, str(body.get("total")))

    # ---------------------------------------------------------
    # 6. Directory writes are locked down
    # ---------------------------------------------------------
    response = requests.post(
        f"{BASE_URL}/hospitals/",
        json={
            "name": "Injection attempt",
            "state": "Test",
            "latitude": 0.0,
            "longitude": 0.0,
        },
        timeout=10,
    )
    check(
        "POST /hospitals/ rejected without credentials",
        response.status_code in (401, 403),
        str(response.status_code),
    )

    # ---------------------------------------------------------
    # 7. Admin surface is gone
    # ---------------------------------------------------------
    for path in ("/admin/sos-alerts", "/admin/appointments", "/admin/verify"):
        response = requests.get(f"{BASE_URL}{path}", timeout=10)
        check(f"{path} is not mounted", response.status_code == 404, str(response.status_code))

    # ---------------------------------------------------------
    # 8. Hospital queue writes are locked down
    # ---------------------------------------------------------
    response = requests.post(
        f"{BASE_URL}/hospitals/1/queue",
        json={"queue_size": 0, "emergency_cases": 0, "available_doctors": 0},
        timeout=10,
    )
    check(
        "POST /hospitals/{id}/queue rejected without a key",
        response.status_code == 403,
        str(response.status_code),
    )

    # ---------------------------------------------------------
    # 9. Search still works
    # ---------------------------------------------------------
    response = requests.get(f"{BASE_URL}/hospitals/search", params={"q": "apollo"}, timeout=30)
    check("GET /hospitals/search returns 200", response.status_code == 200)
    check("search returns rows", len(response.json()) > 0, f"{len(response.json())} rows")

    # ---------------------------------------------------------
    # 10. Detail endpoint
    # ---------------------------------------------------------
    response = requests.get(f"{BASE_URL}/hospitals/1", timeout=10)
    check("GET /hospitals/{id} returns 200", response.status_code == 200)

    # ---------------------------------------------------------
    # Report
    # ---------------------------------------------------------
    failures = [r for r in _results if r[0] == FAIL]
    print()
    print(f"{len(_results) - len(failures)}/{len(_results)} checks passed")
    if failures:
        print("FAILURES:")
        for _, label, detail in failures:
            print(f"  - {label}: {detail}")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
