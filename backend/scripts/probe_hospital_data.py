"""Ad-hoc data-quality probe for the hospitals table. Safe: read-only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import sqlalchemy as sa

engine = sa.create_engine(os.getenv("DATABASE_URL"))

QUERIES = [
    ("total hospitals", "select count(*) from hospitals"),
    (
        "emergency_available = true",
        "select count(*) from hospitals where emergency_available = true",
    ),
    (
        "phone looks real",
        "select count(*) from hospitals where phone is not null "
        "and phone not in ('0', '')",
    ),
    (
        "emergency_phone looks real",
        "select count(*) from hospitals where emergency_phone is not null "
        "and emergency_phone not in ('0', '')",
    ),
    (
        "has city",
        "select count(*) from hospitals where city is not null and city <> ''",
    ),
    (
        "lat range",
        "select min(latitude), max(latitude), min(longitude), max(longitude) "
        "from hospitals",
    ),
    ("distinct states", "select count(distinct state) from hospitals"),
]

with engine.connect() as conn:
    for label, sql in QUERIES:
        row = conn.execute(sa.text(sql)).fetchone()
        print(f"{label:28} {row}")

    cols = conn.execute(
        sa.text(
            "select column_name from information_schema.columns "
            "where table_name = 'hospitals' order by ordinal_position"
        )
    )
    print("\nhospitals columns:")
    print("  " + ", ".join(r[0] for r in cols))
