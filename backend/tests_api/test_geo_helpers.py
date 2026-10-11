"""
Unit tests for the geo helpers behind GET /hospitals/nearby.

These are pure-function tests: no server required.

    python tests_api/test_geo_helpers.py

Guards two historical failure modes:
  1. Double-converting latitude (radians() applied to an already-radian pair),
     which understated distances by ~6x.
  2. A bounding box that does not fully contain the radius circle, which
     silently drops facilities from nearby results.
"""

import os
import random
import sys
from math import cos, radians, sin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.hospitals import bounding_box, haversine_km

# Great-circle reference values (well-known, ~0.5% tolerance is plenty here).
DELHI = (28.6139, 77.2090)
MUMBAI = (19.0760, 72.8777)
CHENNAI = (13.0827, 80.2707)
KOLKATA = (22.5726, 88.3639)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} -- {detail}")
        failures.append(label)


def test_known_distances():
    delhi_mumbai = haversine_km(*DELHI, *MUMBAI)
    check(
        "Delhi->Mumbai is ~1153km",
        1100 <= delhi_mumbai <= 1210,
        f"got {delhi_mumbai:.1f}km",
    )

    chennai_kolkata = haversine_km(*CHENNAI, *KOLKATA)
    check(
        "Chennai->Kolkata is ~1360km",
        1300 <= chennai_kolkata <= 1420,
        f"got {chennai_kolkata:.1f}km",
    )

    zero = haversine_km(*MUMBAI, *MUMBAI)
    check("identical points are 0km", zero == 0.0, f"got {zero}")

    # Regression: the buggy version returned ~195km for a 1153km pair.
    check(
        "distance is not understated",
        delhi_mumbai > 1000,
        f"got {delhi_mumbai:.1f}km -- radians double-conversion is back?",
    )


def test_bbox_contains_circle():
    lat, lon, radius = 19.0760, 72.8777, 10.0
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat, lon, radius)

    # Points exactly on the circle, at 16 bearings, must all be inside the box.
    leaked = []
    for step in range(16):
        bearing_deg = step * 22.5
        bearing = radians(bearing_deg)
        # Local flat-earth offset, then back to degrees.
        dlat = (radius / 110.574) * cos(bearing)
        dlon = (radius / (111.320 * max(abs(cos(radians(lat))), 1e-6))) * sin(bearing)
        plat, plon = lat + dlat, lon + dlon
        if not (min_lat <= plat <= max_lat and min_lon <= plon <= max_lon):
            leaked.append((bearing_deg, plat, plon))

    check("box contains all points on the circle", not leaked, f"leaked={leaked}")

    # Random points strictly inside the radius must all be in the box.
    rng = random.Random(42)
    random_leaks = []
    for _ in range(500):
        dist = rng.uniform(0, radius)
        bearing = radians(rng.uniform(0, 360))
        dlat = (dist / 110.574) * cos(bearing)
        dlon = (dist / (111.320 * max(abs(cos(radians(lat))), 1e-6))) * sin(bearing)
        plat, plon = lat + dlat, lon + dlon
        if not (min_lat <= plat <= max_lat and min_lon <= plon <= max_lon):
            random_leaks.append((dist, plat, plon))

    check(
        "box contains 500 random in-radius points",
        not random_leaks,
        f"leaked={len(random_leaks)}",
    )


def test_bbox_does_not_over_cover():
    """A box far larger than the circle would defeat the point of the filter."""
    lat, lon, radius = 19.0760, 72.8777, 10.0
    min_lat, max_lat, _, _ = bounding_box(lat, lon, radius)
    height_deg = max_lat - min_lat

    # ~1 degree of latitude is ~110km, so a 10km radius should span ~0.18deg.
    check(
        "box height is tight (~0.18deg for 10km)",
        0.15 <= height_deg <= 0.22,
        f"got {height_deg:.4f}deg",
    )

    # Near the poles cos(lat)->0; the guard must keep the box finite.
    polar = bounding_box(89.9, 0.0, radius)
    check(
        "box stays finite near the pole",
        all(abs(v) < 1000 for v in polar),
        f"got {polar}",
    )


def main():
    test_known_distances()
    test_bbox_contains_circle()
    test_bbox_does_not_over_cover()

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        sys.exit(1)
    print("ALL GEO TESTS PASSED")


if __name__ == "__main__":
    main()
