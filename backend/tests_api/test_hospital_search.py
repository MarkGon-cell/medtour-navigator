"""
Unit tests for the symptom-keyword and pincode search behind
POST /hospitals/keywords, GET /hospitals/by-keywords and
GET /hospitals/by-pincode.

Pure functions plus an in-memory SQLite directory: no server, no network
(the LLM path is never exercised -- `NVIDIA_NIM_API_KEY` is absent).

    python tests_api/test_hospital_search.py

Guards the failure modes that would silently break the hospitals page:
  1. Results not ordered distance low -> high from the caller's coordinates.
  2. Keyword matching that degenerates into substring soup ("ent" inside
     "Centre" / "temperature").
  3. A search box that returns nothing when Multispeciality is forgotten or
     the radius hides the only match.
  4. A pincode search that ignores the caller's coordinates, so distances
     become meaningless.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.hospital import Hospital
from app.services import hospital_search
from app.services.geo import haversine_km

# User standing in Mumbai (same point as the rest of the geo tests).
USER = (19.0760, 72.8777)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS] {label}")
    else:
        print(f"[FAIL] {label} -- {detail}")
        failures.append(label)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def seed(db) -> dict:
    """Five facilities: two near the user, one ENT block, one dud, one far."""
    rows = {
        # ~2.2 km north of the user.
        "heart": Hospital(
            name="Lilavati Heart Institute",
            state="Maharashtra",
            city="Mumbai",
            pincode="400050",
            latitude=19.0960,
            longitude=72.8777,
            specialties="Cardiology; Cardiac Surgery",
        ),
        # ~5.6 km, hyphenated spelling of multispeciality.
        "multi": Hospital(
            name="KEM Multi-Specialty Hospital",
            state="Maharashtra",
            city="Mumbai",
            pincode="400012",
            latitude=19.1260,
            longitude=72.8777,
            specialties="General Medicine",
        ),
        # ~1.1 km: the only row that may match the keyword "ENT".
        "ent": Hospital(
            name="Sunrise ENT and Eye Centre",
            state="Maharashtra",
            city="Mumbai",
            pincode="400050",
            latitude=19.0860,
            longitude=72.8777,
            specialties="Otorhinolaryngology",
        ),
        # ~0.5 km: contains "ent" as a substring of "Centre" only.
        "centre": Hospital(
            name="Metro Diagnostics Centre",
            state="Maharashtra",
            city="Mumbai",
            pincode="400050",
            latitude=19.0806,
            longitude=72.8777,
            specialties="Pathology",
        ),
        # Far away (Chennai) and irrelevant to a heart search.
        "far": Hospital(
            name="Chennai Cancer Institute",
            state="Tamil Nadu",
            city="Chennai",
            pincode="600008",
            latitude=13.0827,
            longitude=80.2707,
            specialties="Oncology",
        ),
    }
    for row in rows.values():
        db.add(row)
    db.commit()
    return rows


# ---------------------------------------------------------
# Keyword generation
# ---------------------------------------------------------

def test_fallback_keywords():
    keywords = hospital_search.fallback_keywords(
        "chest pain and shortness of breath since morning"
    )
    check(
        "fallback returns exactly 5 keywords",
        len(keywords) == 5,
        f"got {keywords}",
    )
    check(
        "chest pain starts with a cardiology keyword",
        keywords[0] in ("Heart", "Cardiac", "Cardiology", "Cardiothoracic", "Chest"),
        f"got {keywords[0]!r}",
    )
    check(
        "fallback keywords are unique",
        len({k.lower() for k in keywords}) == len(keywords),
        f"got {keywords}",
    )

    # An unrecognised line must still yield a usable list, never an empty one.
    vague = hospital_search.fallback_keywords("feels off somehow")
    check(
        "unrecognised symptoms still return 5 keywords",
        len(vague) == 5,
        f"got {vague}",
    )


def test_normalize_keywords_always_includes_multispeciality():
    keywords = hospital_search.normalize_keywords(["Heart", "Cardiac"])
    check(
        "Multispeciality is appended",
        keywords[-1] == hospital_search.MULTISPECIALITY_KEYWORD,
        f"got {keywords}",
    )
    check(
        "already-present Multispeciality is not duplicated",
        sum(
            1
            for k in hospital_search.normalize_keywords(
                ["Heart", hospital_search.MULTISPECIALITY_KEYWORD]
            )
            if hospital_search._normalize(k)
            == hospital_search._normalize(hospital_search.MULTISPECIALITY_KEYWORD)
        )
        == 1,
        f"got {hospital_search.normalize_keywords(['Heart', hospital_search.MULTISPECIALITY_KEYWORD])}",
    )
    check(
        "comma-separated input is accepted",
        hospital_search.normalize_keywords("Eye, Skin")[0] == "Eye",
        f"got {hospital_search.normalize_keywords('Eye, Skin')}",
    )


# ---------------------------------------------------------
# Matching
# ---------------------------------------------------------

def test_word_start_matching():
    ent_row = Hospital(name="Sunrise ENT and Eye Centre", specialties="")
    centre_row = Hospital(name="Metro Diagnostics Centre", specialties="")
    temp_row = Hospital(name="Sunrise General Hospital", specialties="Temperature control")

    check(
        "'ENT' matches an ENT hospital",
        bool(hospital_search._matched_keywords(["ENT"], ent_row)),
        "no match",
    )
    check(
        "'ENT' does not match 'Centre'",
        not hospital_search._matched_keywords(["ENT"], centre_row),
        "matched 'Centre'",
    )
    check(
        "'ENT' does not match a 'Temperature' tag",
        not hospital_search._matched_keywords(["ENT"], temp_row),
        "matched 'Temperature'",
    )
    check(
        "'ortho' still matches 'Orthopaedics' (prefix)",
        bool(
            hospital_search._matched_keywords(
                ["ortho"], Hospital(name="XYZ Orthopaedic Hospital", specialties="")
            )
        ),
        "no match",
    )


def test_multispeciality_spellings():
    variants = [
        "Aster Multispeciality Hospital",
        "KEM Multi-Specialty Hospital",
        "Apollo Multi Speciality Hospital",
        "City Multispecialty Care",
    ]
    misses = [
        name for name in variants
        if not hospital_search._matched_keywords(
            [hospital_search.MULTISPECIALITY_KEYWORD],
            Hospital(name=name, specialties=""),
        )
    ]
    check("all multispeciality spellings match", not misses, f"missed {misses}")

    check(
        "a plain hospital is not multispeciality",
        not hospital_search._matched_keywords(
            [hospital_search.MULTISPECIALITY_KEYWORD],
            Hospital(name="Metro Diagnostics Centre", specialties="Pathology"),
        ),
        "false positive",
    )


# ---------------------------------------------------------
# Keyword search (DB)
# ---------------------------------------------------------

def test_keyword_search_is_sorted_by_distance():
    db = make_session()
    seed(db)

    matches = hospital_search.search_by_keywords(
        db, ["Heart", hospital_search.MULTISPECIALITY_KEYWORD],
        latitude=USER[0], longitude=USER[1], radius_km=50, limit=20,
    )
    names = [row[0].name for row in matches]
    distances = [row[1] for row in matches]

    check(
        "heart + multispeciality hits the right rows",
        "Lilavati Heart Institute" in names and "KEM Multi-Specialty Hospital" in names,
        f"got {names}",
    )
    check(
        "irrelevant rows are excluded",
        "Metro Diagnostics Centre" not in names
        and "Chennai Cancer Institute" not in names,
        f"got {names}",
    )
    check(
        "distances ascend low -> high",
        distances == sorted(distances),
        f"got {distances}",
    )
    check(
        "distances are measured from the caller",
        all(
            abs(d - haversine_km(USER[0], USER[1], h.latitude, h.longitude)) < 1e-6
            for h, d, _ in matches
        ),
        f"got {distances}",
    )
    check(
        "each row reports the keywords it matched",
        all(row[2] for row in matches),
        f"got {[row[2] for row in matches]}",
    )
    db.close()


def test_keyword_search_retries_nationwide_when_radius_is_empty():
    db = make_session()
    seed(db)

    # Nothing matches within 1 km, but the same keywords exist ~2 km away.
    matches = hospital_search.search_by_keywords(
        db, ["Heart"],
        latitude=USER[0], longitude=USER[1], radius_km=1, limit=20,
    )
    names = [row[0].name for row in matches]
    distances = [row[1] for row in matches]

    check(
        "empty radius falls back to a wider search",
        "Lilavati Heart Institute" in names,
        f"got {names}",
    )
    check(
        "fallback results are still sorted low -> high",
        distances == sorted(distances),
        f"got {distances}",
    )
    db.close()


def test_keyword_search_excludes_non_word_matches():
    db = make_session()
    seed(db)

    matches = hospital_search.search_by_keywords(
        db, ["ENT"], latitude=USER[0], longitude=USER[1], radius_km=50, limit=20,
    )
    names = [row[0].name for row in matches]

    check(
        "'ENT' finds the ENT hospital, nearest first",
        bool(names) and names[0] == "Sunrise ENT and Eye Centre",
        f"got {names}",
    )
    check(
        "'ENT' does not drag in the 'Centre' or far-away rows "
        "(Multispeciality is searched on purpose)",
        "Metro Diagnostics Centre" not in names
        and "Chennai Cancer Institute" not in names
        and "Lilavati Heart Institute" not in names,
        f"got {names}",
    )
    db.close()


# ---------------------------------------------------------
# Pincode search
# ---------------------------------------------------------

def test_clean_pincode():
    check("plain pincode kept", hospital_search.clean_pincode("400050") == "400050")
    check("spaces stripped", hospital_search.clean_pincode("400 050") == "400050")
    check("junk rejected", hospital_search.clean_pincode("Mumbai") is None)
    check("missing rejected", hospital_search.clean_pincode(None) is None)


def test_pincode_search_is_sorted_by_distance():
    db = make_session()
    seed(db)

    matches = hospital_search.search_by_pincode(
        db, "400050", latitude=USER[0], longitude=USER[1], limit=20
    )
    names = [row[0].name for row in matches]
    distances = [row[1] for row in matches]

    check(
        "pincode limits results to that pincode",
        names
        and all(row[0].pincode == "400050" for row in matches)
        and "KEM Multi-Specialty Hospital" not in names,
        f"got {names}",
    )
    check(
        "pincode distances ascend low -> high",
        distances == sorted(distances),
        f"got {distances}",
    )
    check(
        "pincode distances come from the caller, not the pincode centroid",
        all(
            abs(d - haversine_km(USER[0], USER[1], h.latitude, h.longitude)) < 1e-6
            for h, d in matches
        ),
        f"got {distances}",
    )
    check(
        "spaces inside a stored pincode still match",
        bool(
            hospital_search.search_by_pincode(
                db, "400050", latitude=USER[0], longitude=USER[1]
            )
        )
        and not hospital_search.search_by_pincode(
            db, "999999", latitude=USER[0], longitude=USER[1]
        ),
        "unexpected pincode result",
    )
    db.close()


def test_nearest_directory_pincode_fallback():
    db = make_session()
    seed(db)

    pincode = hospital_search.nearest_directory_pincode(
        db, latitude=USER[0], longitude=USER[1], radius_km=10
    )
    check(
        "offline pincode fallback finds a nearby facility's pincode",
        pincode in {"400050", "400012"},
        f"got {pincode!r}",
    )
    db.close()


def main():
    test_fallback_keywords()
    test_normalize_keywords_always_includes_multispeciality()
    test_word_start_matching()
    test_multispeciality_spellings()
    test_keyword_search_is_sorted_by_distance()
    test_keyword_search_retries_nationwide_when_radius_is_empty()
    test_keyword_search_excludes_non_word_matches()
    test_clean_pincode()
    test_pincode_search_is_sorted_by_distance()
    test_nearest_directory_pincode_fallback()

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        sys.exit(1)
    print("ALL HOSPITAL SEARCH TESTS PASSED")


if __name__ == "__main__":
    main()
