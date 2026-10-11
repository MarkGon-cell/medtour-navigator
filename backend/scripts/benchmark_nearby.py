"""
Benchmark: full-table scan vs bounding-box pre-filter for /hospitals/nearby.

The previous implementation called db.query(Hospital).all() and ran the
haversine over every row in Python. This measures both paths on real data.
"""

import os
import sys
import time
from math import atan2, cos, radians, sin, sqrt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.models.hospital import Hospital

engine = sa.create_engine(os.getenv("DATABASE_URL"))
Session = sessionmaker(bind=engine)

LAT, LON, RADIUS = 19.0760, 72.8777, 10.0


def haversine(lat1, lon1, lat2, lon2):
    # NOTE: convert the raw degree deltas, not an already-radian pair.
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    return 6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a))


def old_path(db):
    """Every row into Python, exact distance, then radius filter."""
    rows = db.query(Hospital).all()
    hits = 0
    for row in rows:
        if haversine(LAT, LON, row.latitude, row.longitude) <= RADIUS:
            hits += 1
    return len(rows), hits


def new_path(db):
    """SQL bounding box first, then exact distance on candidates."""
    dlat = RADIUS / 110.574
    dlon = RADIUS / (111.320 * max(abs(cos(radians(LAT))), 1e-6))

    rows = (
        db.query(Hospital)
        .filter(
            Hospital.latitude >= LAT - dlat,
            Hospital.latitude <= LAT + dlat,
            Hospital.longitude >= LON - dlon,
            Hospital.longitude <= LON + dlon,
        )
        .all()
    )
    hits = 0
    for row in rows:
        if haversine(LAT, LON, row.latitude, row.longitude) <= RADIUS:
            hits += 1
    return len(rows), hits


def bench(label, fn, runs=5):
    db = Session()
    try:
        fn(db)  # warm up
        best = float("inf")
        result = None
        for _ in range(runs):
            start = time.perf_counter()
            result = fn(db)
            best = min(best, time.perf_counter() - start)
    finally:
        db.close()
    print(f"{label:38} {best * 1000:8.1f} ms   scanned={result[0]:6}  hits={result[1]}")
    return best


def main():
    db = Session()
    total = db.query(sa.func.count(Hospital.id)).scalar()
    db.close()
    print(f"hospitals table: {total} rows   target: {LAT},{LON} r={RADIUS}km\n")

    old = bench("full scan + haversine (old)", old_path)
    new = bench("bounding box + haversine (new)", new_path)

    print(f"\nspeedup: {old / new:.1f}x   ({old * 1000:.1f}ms -> {new * 1000:.1f}ms)")


if __name__ == "__main__":
    main()
