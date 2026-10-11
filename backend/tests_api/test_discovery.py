"""
Tests for facility discovery: deduplication, persistence, and the endpoint.

    python tests_api/test_discovery.py

Part 1 is pure-function (no network, no database).
Part 2 touches the real `hospitals` table and cleans up after itself by
       `external_id` -- it inserts two synthetic rows and deletes them in a
       `finally` block, so an assertion failure cannot leave debris behind.
Part 3 calls the live endpoint.

The point of Part 2 is the product rule: **new facilities get stored, existing
ones never get inserted twice and never get overwritten.**
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} -- {detail}")
        failures.append(label)


# ---------------------------------------------------------
# Part 1: name matching and duplicate detection (pure)
# ---------------------------------------------------------

from app.services.discovery import (  # noqa: E402
    Facility,
    _in_india,
    _looks_usable,
    find_duplicate,
    names_match,
    normalize_name,
)


def test_name_matching() -> None:
    check(
        "plural/suffix variants match",
        names_match("Apollo Hospital", "Apollo Hospitals Ltd"),
        normalize_name("Apollo Hospitals Ltd"),
    )
    check(
        "qualifier variant matches",
        names_match("City Hospital", "City Hospital for Women and Children"),
    )
    check("different hospitals do not match", not names_match("Apollo Hospital", "Fortis Memorial"))
    check("empty name never matches", not names_match("", "Apollo Hospital"))
    check("None never matches", not names_match(None, None))

    # Short names are matched on token overlap rather than substring, so a
    # 3-letter name can never swallow an unrelated long name.
    check(
        "short name matches via token overlap",
        names_match("SMS Hospital", "SMS Hospital Jaipur"),
    )
    check(
        "short unrelated name does not match",
        not names_match("AIIMS", "Fortis Hospital"),
    )


def _facility(name: str, lat: float, lon: float, **kwargs) -> Facility:
    defaults = dict(source="overpass", latitude=lat, longitude=lon, name=name)
    defaults.update(kwargs)
    return Facility(**defaults)


def test_duplicate_detection() -> None:
    existing = _facility("Apollo Hospital", 19.0760, 72.8777)

    # Same site, completely different mapped name -> still one facility.
    same_site = _facility("Apollo Hospitals Banjara Hills", 19.0762, 72.8780)
    check(
        "same site (few metres) counts as duplicate",
        find_duplicate(same_site, [existing]) is not None,
    )

    # ~300 m away with a matching name -> duplicate.
    near_named = _facility("Apollo Hospital", 19.0785, 72.8777)
    check(
        "nearby + matching name counts as duplicate",
        find_duplicate(near_named, [existing]) is not None,
    )

    # 2 km away with an identical name -> NOT a duplicate (chain hospitals).
    far_same_name = _facility("Apollo Hospital", 19.0580, 72.8777)
    check(
        "far facility with identical name is kept",
        find_duplicate(far_same_name, [existing]) is None,
    )

    # external_id wins regardless of distance (coordinates drifted upstream).
    by_id = _facility("Renamed Facility", 12.0, 75.0, external_id="osm/way/42")
    holder = _facility("Old Name", 12.5, 75.5, external_id="osm/way/42")
    check(
        "matching external_id wins even when far apart",
        find_duplicate(by_id, [holder]) is not None,
    )


def test_guards() -> None:
    check("Mumbai is in India", _in_india(19.0760, 72.8777))
    check("London is not in India", not _in_india(51.5074, -0.1278))
    check(
        "facility without a name is rejected",
        _looks_usable(_facility("  ", 19.0, 72.0)) == "missing_name",
    )
    check(
        "facility outside India is rejected",
        _looks_usable(_facility("Somewhere Hospital", 40.7, -74.0)) == "outside_india",
    )
    check(
        "ordinary Indian facility passes the guard",
        _looks_usable(_facility("Wardha General Hospital", 21.0, 79.0)) is None,
    )


def test_state_inference() -> None:
    """
    Regression test for a real bug.

    The CSV ships six Lucknow rows whose `state` is wrong in every case --
    Bihar, Chhattisgarh, Haryana x3, Jammu and Kashmir. Inheriting the *nearest*
    directory row's state stamped fabricated states onto two freshly discovered
    Lucknow facilities. Two corrections: inference now votes over the provider
    batch rather than the directory, and requires a supermajority.
    """
    from app.models.hospital import Hospital
    from app.services.discovery import _infer_state, state_consensus

    def batch(states: list) -> list[Facility]:
        """Facilities laid out on a small grid around Lucknow."""
        return [
            Facility(name=f"found {i}", latitude=26.80 + i * 0.001,
                     longitude=80.90 + i * 0.001, source="overpass", state=state)
            for i, state in enumerate(states)
        ]

    # The measured Overpass batch: 181 of 214 Lucknow hospitals declare
    # "Uttar Pradesh", the rest declare nothing.
    states = ["Uttar Pradesh"] * 98 + [None, None]
    facilities = batch(states)

    untagged = [f for f in facilities if f.state is None]
    check(
        "untagged facilities inherit the provider majority",
        all(_infer_state(f, facilities) == "Uttar Pradesh" for f in untagged),
        str([_infer_state(f, facilities) for f in untagged]),
    )

    # A genuinely split batch must report nothing rather than pick a side.
    # (Exercised via state_consensus: _infer_state would short-circuit and
    # return each facility's own already-present state.)
    split = batch(["Haryana"] * 3 + ["Bihar"] * 3)
    check(
        "a split batch invents no state",
        all(
            state_consensus(f.latitude, f.longitude, split) is None
            for f in split
        ),
        str([state_consensus(f.latitude, f.longitude, split) for f in split]),
    )

    # Too few neighbours -> say nothing.
    check(
        "thin batch means no invented state",
        state_consensus(26.85, 80.95, batch([None, None])) is None,
    )

    # A provider-reported state always wins over inference.
    stated = batch(["Uttar Pradesh"] * 5)
    target = Facility(name="Found Hospital", latitude=26.85, longitude=80.95,
                      source="overpass", state="Maharashtra")
    check(
        "provider-reported state is used verbatim",
        _infer_state(target, stated) == "Maharashtra",
    )

    # The corrupt CSV neighbourhood must never be the population consulted.
    csv_rows = [
        Hospital(name="csv", state=state, latitude=lat, longitude=lon)
        for state, lat, lon in [
            ("Bihar", 26.8745, 80.9819),
            ("Chhattisgarh", 26.8181, 80.9496),
            ("Haryana", 26.8031, 80.8909),
            ("Haryana", 26.8677, 81.0144),
            ("Haryana", 26.8873, 80.9940),
            ("Jammu and Kashmir", 26.8984, 80.9629),
        ]
    ]
    # The corrupt CSV neighbourhood must never be the population consulted:
    # voting over it produces a wrong or absent answer, the batch produces UP.
    probe = Facility(name="x", latitude=26.85, longitude=80.95,
                     source="overpass", state=None)
    check(
        "voting over the directory answers wrongly",
        _infer_state(probe, csv_rows) != "Uttar Pradesh",
        str(_infer_state(probe, csv_rows)),
    )
    check(
        "voting over the provider batch answers correctly",
        _infer_state(probe, facilities) == "Uttar Pradesh",
        str(_infer_state(probe, facilities)),
    )


def test_cache_hit_path() -> None:
    """
    Regression test for a bug that only manifests on a **second** request.

    `_cached_fetch` stored the `(facilities, status)` pair and then returned
    that pair as the facilities list on a hit. The caller does
    `overpass_rows + geoapify_rows`, so the first request in a TTL window
    worked and the next one raised
    `TypeError: can only concatenate list (not "tuple") to list` -> 500.
    Cold servers hid it, which is exactly why it needs pinning down here.
    """
    from app.services import discovery

    discovery.clear_cache()
    calls: list[int] = []

    def fake(latitude, longitude, radius_km):
        calls.append(1)
        return [_facility("Cached Hospital", latitude, longitude)], "ok"

    rows_first, status_first = discovery._cached_fetch(
        "fake-provider", 26.85, 80.95, 5.0, fake
    )
    rows_second, status_second = discovery._cached_fetch(
        "fake-provider", 26.85, 80.95, 5.0, fake
    )

    try:
        check("first call reaches the provider", status_first == "ok" and len(calls) == 1)
        check("second call is served from cache", status_second == "cached" and len(calls) == 1)
        check(
            "a cache hit still yields a list",
            isinstance(rows_second, list),
            str(type(rows_second)),
        )
        check(
            "a cache hit yields the facilities, not the (facilities, status) pair",
            len(rows_second) == 1 and rows_second[0].name == "Cached Hospital",
            str(rows_second)[:80],
        )
        check(
            "cached and fresh results still concatenate",
            isinstance(rows_first + rows_second, list),
        )
    finally:
        discovery.clear_cache()


# ---------------------------------------------------------
# Part 2: persistence is additive and idempotent (real DB)
# ---------------------------------------------------------

MARKER_ID = "osm/node/medtour-discovery-test"


def test_persist_new_is_idempotent() -> None:
    from app.database.database import SessionLocal
    from app.models.hospital import Hospital
    from app.services.discovery import persist_new

    db = SessionLocal()
    try:
        # Clean slate from any earlier aborted run.
        db.query(Hospital).filter(
            Hospital.external_id.in_([MARKER_ID, "geoapify/test-2"])
        ).delete(synchronize_session=False)
        db.commit()

        first = _facility(
            "MedTour Test Hospital",
            21.1000,
            79.1000,
            external_id=MARKER_ID,
            state="TestState",
        )
        inserted, _existing, invalid = persist_new(db, [first], existing=[])

        check("first insert creates a row", len(inserted) == 1, f"{len(inserted)}")
        check("first insert rejects nothing", invalid == 0, str(invalid))
        check("first facility marked stored", first.stored is True)

        count = (
            db.query(Hospital)
            .filter(Hospital.external_id == MARKER_ID)
            .count()
        )
        check("row is in Postgres", count == 1, str(count))

        # The same place reported again by the other provider: different
        # external_id, different name casing, ~10 m away.
        second = _facility(
            "medtour test hospital",
            21.10010,
            79.10010,
            source="geoapify",
            external_id="geoapify/test-2",
            state="TestState",
        )
        inserted_again, skipped, _invalid = persist_new(
            db, [second], existing=inserted
        )

        check("second insert is a no-op", len(inserted_again) == 0, str(len(inserted_again)))
        check("second facility reported as existing", skipped == 1, str(skipped))
        check(
            "second facility reason is already_in_directory",
            second.reason == "already_in_directory",
            str(second.reason),
        )

        count = (
            db.query(Hospital)
            .filter(
                Hospital.external_id.in_([MARKER_ID, "geoapify/test-2"])
            )
            .count()
        )
        check("still exactly one row after re-search", count == 1, str(count))

        # And the original row was not overwritten by the second pass.
        row = db.query(Hospital).filter(Hospital.external_id == MARKER_ID).first()
        check(
            "existing row was not overwritten",
            row is not None and row.name == "MedTour Test Hospital",
            getattr(row, "name", None),
        )
        check(
            "existing row keeps its original source",
            row is not None and row.source == "overpass",
            getattr(row, "source", None),
        )
    finally:
        db.query(Hospital).filter(
            Hospital.external_id.in_([MARKER_ID, "geoapify/test-2"])
        ).delete(synchronize_session=False)
        db.commit()
        leftover = (
            db.query(Hospital)
            .filter(Hospital.external_id.in_([MARKER_ID, "geoapify/test-2"]))
            .count()
        )
        db.close()
        check("test rows cleaned up", leftover == 0, str(leftover))


# ---------------------------------------------------------
# Part 3: live endpoint
# ---------------------------------------------------------

BASE_URL = os.environ.get("MEDTOUR_BASE_URL", "http://127.0.0.1:8000")


def test_discover_endpoint() -> None:
    import requests

    response = requests.get(
        f"{BASE_URL}/hospitals/discover",
        params={
            "latitude": 19.0760,
            "longitude": 72.8777,
            "radius_km": 5,
            "limit": 10,
            "persist": "false",
        },
        timeout=60,
    )
    check("GET /hospitals/discover returns 200", response.status_code == 200, str(response.status_code))
    body = response.json()

    check("response wraps results", isinstance(body.get("results"), list))
    check("reports every source", set(body.get("sources", {})) == {"local", "overpass", "geoapify"}, str(body.get("sources")))
    check("reports stats", "stats" in body and "persisted" in body.get("stats", {}))
    check("degraded flag present", isinstance(body.get("degraded"), bool))

    # persist=false must be honoured even when providers return something.
    check(
        "persist=false writes nothing",
        body.get("stats", {}).get("persisted") == 0,
        str(body.get("stats")),
    )

    # Existing rows must be marked stored and local.
    results = body.get("results", [])
    if results:
        check(
            "local rows flagged origin=local",
            all(r.get("origin") == "local" for r in results if r.get("stored")),
            str({r.get("origin") for r in results}),
        )
        distances = [r["distance_km"] for r in results]
        check("results sorted nearest-first", distances == sorted(distances))

    # Degraded must be reported honestly rather than raising.
    if body["sources"]["overpass"] == "unreachable":
        check(
            "unreachable providers are reported, not hidden",
            body["degraded"] is True,
            str(body),
        )
        print(f"       (overpass={body['sources']['overpass']}, "
              f"geoapify={body['sources']['geoapify']})")


def main() -> None:
    print("--- Part 1: pure functions ---")
    test_name_matching()
    test_duplicate_detection()
    test_guards()
    test_state_inference()
    test_cache_hit_path()

    print("\n--- Part 2: persistence against Postgres ---")
    test_persist_new_is_idempotent()

    print("\n--- Part 3: live endpoint ---")
    try:
        test_discover_endpoint()
    except Exception as exc:  # noqa: BLE001
        check("endpoint reachable", False, f"{type(exc).__name__}: {exc}")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for label in failures:
            print(f"  - {label}")
        sys.exit(1)
    print("ALL DISCOVERY TESTS PASSED")


if __name__ == "__main__":
    main()
