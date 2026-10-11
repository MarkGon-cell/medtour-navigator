"""
Symptom-keyword and pincode search over the hospital directory.

The hospitals page needs three related things, and all three must agree on
what "distance from me" means:

1. ``generate_search_keywords()`` -- turn a free-text symptom line into the
   5 short keywords most likely to appear in an Indian hospital's *name*
   ("Heart", "Cardiac", "Eye", ...). An LLM does this; a deterministic
   symptom table keeps the search box working when NIM is unreachable.
2. ``search_by_keywords()`` -- match those keywords (Multispeciality always
   included) against the name/specialty/facility columns and return the hits
   nearest-first.
3. ``resolve_pincode()`` + ``search_by_pincode()`` -- derive the caller's
   pincode from their coordinates, then list that pincode's hospitals,
   nearest-first.

Every distance comes from ``app.services.geo.haversine_km``, so this module,
``GET /hospitals/nearby`` and ``app.services.discovery`` cannot drift apart.

Regression-tested by backend/tests_api/test_hospital_search.py.
"""

import os
import re
import threading
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple

import requests
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.services.geo import bounding_box, haversine_km

# How many symptom keywords the AI is asked for (spec: exactly 5).
KEYWORD_COUNT = 5

# Always searched alongside the symptom keywords: multispeciality hospitals
# are in scope no matter what the symptoms are. The `%` gap bridges the
# space/hyphen/underscore the directory uses between "multi" and "special".
MULTISPECIALITY_KEYWORD = "Multispeciality"
_MULTISPECIALITY_SQL_PATTERN = "%multi%special%"
_MULTISPECIALITY_RE = re.compile(r"\bmulti\s*special")

# Columns a keyword may hit. `name` is the primary target (the spec asks for
# keywords "that may come in hospital name"); the rest catch department-only
# matches such as a "Cardiology" tag on an unnamed speciality block.
_MATCH_COLUMNS = (
    Hospital.name,
    Hospital.specialties,
    Hospital.facilities,
    Hospital.category,
    Hospital.care_type,
    Hospital.discipline,
)


# ---------------------------------------------------------
# Symptom -> name-keyword table (LLM fallback)
# ---------------------------------------------------------

_HEART = ("Heart", "Cardiac", "Cardiology", "Cardiothoracic", "Chest")
_RESPIRATORY = ("Chest", "Pulmonary", "Respiratory", "Lung", "Asthma")
_NEURO = ("Brain", "Neuro", "Neurology", "Neurosciences", "Stroke")
_ORTHO = ("Ortho", "Orthopaedic", "Orthopedic", "Bone", "Joint")
_GASTRO = ("Gastro", "Gastroenterology", "Liver", "Digestive", "Stomach")
_WOMEN = ("Women", "Maternity", "Obstetrics", "Gynaecology", "Gynecology")
_SKIN = ("Skin", "Dermatology", "Derma", "Allergy")
_RENAL = ("Kidney", "Renal", "Urology", "Urology Care")
_EYE = ("Eye", "Ophthalmology", "Vision", "Netra", "Retina")
_ENT = ("ENT", "Nose", "Throat", "Hearing", "Ear")
_ONCOLOGY = ("Cancer", "Oncology", "Tumour", "Tumor")
_DIABETES = ("Diabetes", "Endocrine", "Thyroid")
_TRAUMA = ("Trauma", "Emergency", "Accident", "Burn")
_CHILD = ("Child", "Children", "Paediatric", "Pediatric", "Kids")
_DENTAL = ("Dental", "Oral", "Teeth")
_MIND = ("Psychiatry", "Psychology", "Mental")
_GENERAL = ("General", "Medicine", "Clinic", "Hospital")

# Ordered specific -> generic so the first hits keep the most useful words.
# Keys are lower-case fragments matched against the normalised symptom text.
SYMPTOM_NAME_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("chest", _HEART),
    ("heart", _HEART),
    ("cardiac", _HEART),
    ("palpitation", _HEART),
    ("blood pressure", _HEART),
    ("hypertension", _HEART),
    ("breath", _RESPIRATORY),
    ("cough", _RESPIRATORY),
    ("asthma", _RESPIRATORY),
    ("pneumonia", _RESPIRATORY),
    ("lung", _RESPIRATORY),
    ("respiratory", _RESPIRATORY),
    ("headache", _NEURO),
    ("migraine", _NEURO),
    ("seizure", _NEURO),
    ("stroke", _NEURO),
    ("numb", _NEURO),
    ("dizz", _NEURO),
    ("vertigo", _NEURO),
    ("brain", _NEURO),
    ("neuro", _NEURO),
    ("fracture", _ORTHO),
    ("bone", _ORTHO),
    ("joint", _ORTHO),
    ("knee", _ORTHO),
    ("hip", _ORTHO),
    ("spine", _ORTHO),
    ("back pain", _ORTHO),
    ("sprain", _ORTHO),
    ("ortho", _ORTHO),
    ("stomach", _GASTRO),
    ("abdominal", _GASTRO),
    ("abdomen", _GASTRO),
    ("nausea", _GASTRO),
    ("vomit", _GASTRO),
    ("diarrhea", _GASTRO),
    ("diarrhoea", _GASTRO),
    ("liver", _GASTRO),
    ("gastro", _GASTRO),
    ("pregnan", _WOMEN),
    ("gynaec", _WOMEN),
    ("gynec", _WOMEN),
    ("menstru", _WOMEN),
    ("delivery", _WOMEN),
    ("women", _WOMEN),
    ("rash", _SKIN),
    ("itch", _SKIN),
    ("skin", _SKIN),
    ("dermat", _SKIN),
    ("kidney", _RENAL),
    ("urolog", _RENAL),
    ("eye", _EYE),
    ("vision", _EYE),
    ("sight", _EYE),
    ("ophthalm", _EYE),
    ("ear", _ENT),
    ("nose", _ENT),
    ("throat", _ENT),
    ("cancer", _ONCOLOGY),
    ("tumour", _ONCOLOGY),
    ("tumor", _ONCOLOGY),
    ("oncolog", _ONCOLOGY),
    ("diabet", _DIABETES),
    ("sugar", _DIABETES),
    ("thyroid", _DIABETES),
    ("accident", _TRAUMA),
    ("trauma", _TRAUMA),
    ("burn", _TRAUMA),
    ("bleed", _TRAUMA),
    ("emergency", _TRAUMA),
    ("unconscious", _TRAUMA),
    ("choking", _TRAUMA),
    ("child", _CHILD),
    ("baby", _CHILD),
    ("paediatric", _CHILD),
    ("pediatric", _CHILD),
    ("dental", _DENTAL),
    ("tooth", _DENTAL),
    ("psych", _MIND),
    ("anxiety", _MIND),
    ("depression", _MIND),
    ("fever", _GENERAL),
    ("temperature", _GENERAL),
    ("infection", _GENERAL),
    ("cold", _GENERAL),
    ("flu", _GENERAL),
)


def _normalize(value: object) -> str:
    """Lower-case, punctuation-free haystack text (shared by SQL + Python)."""
    if value is None:
        return ""
    text = str(value).lower().replace("&", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=256)
def _keyword_regex(keyword: str):
    """
    Word-START match, not a bare substring.

    "ent" must not hit "Centre"/"patient"/"temperature", while "ortho" still
    has to hit "Orthopaedics". Both need the keyword to begin a word.
    """
    return re.compile(r"\b" + re.escape(_normalize(keyword)))


def fallback_keywords(symptoms: str) -> List[str]:
    """Deterministic keyword list used when the LLM is unreachable."""
    text = _normalize(symptoms)

    found: List[str] = []
    seen = set()
    for fragment, keywords in SYMPTOM_NAME_KEYWORDS:
        if fragment not in text:
            continue
        for keyword in keywords:
            key = keyword.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(keyword)
            if len(found) == KEYWORD_COUNT:
                return found

    if not found:
        # Nothing recognised (or an empty line): nearest general facility is
        # the correct answer, and Multispeciality is searched regardless.
        found.extend(["General", "Clinic"])

    # Top the list up so callers always receive KEYWORD_COUNT keywords.
    for keyword in _GENERAL:
        if len(found) >= KEYWORD_COUNT:
            break
        if keyword.lower() not in seen:
            seen.add(keyword.lower())
            found.append(keyword)

    return found[:KEYWORD_COUNT]


def _clean_keywords(raw: object) -> List[str]:
    """Keep ASCII word-only keywords, de-duplicated, capped at 5."""
    cleaned: List[str] = []
    seen = set()

    if not isinstance(raw, (list, tuple)):
        return cleaned

    for item in raw:
        if not isinstance(item, str):
            continue
        keyword = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 ]+", " ", item)).strip()
        if not keyword or len(keyword) > 30:
            continue
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(" ".join(word.capitalize() for word in keyword.split()))
        if len(cleaned) == KEYWORD_COUNT:
            break

    return cleaned


# ---------------------------------------------------------
# 1. AI keyword generation
# ---------------------------------------------------------

_KEYWORD_SYSTEM_PROMPT = (
    "You convert a patient's symptom description into SEARCH KEYWORDS for an "
    "Indian hospital directory.\n"
    "Return ONLY a valid JSON object (no markdown) of the form "
    '{"keywords": ["...", "...", "...", "...", "..."]} with EXACTLY '
    f"{KEYWORD_COUNT} keywords.\n"
    "Each keyword is a short term (1-3 words, at most 20 characters) that "
    "could plausibly appear in a HOSPITAL'S NAME or in its specialty tag -- "
    'for example chest pain -> "Heart", "Cardiac", "Cardiology"; blurred '
    'vision -> "Eye", "Ophthalmology".\n'
    "Rules: ASCII letters and single spaces only (no punctuation), every "
    "keyword unique, no sentences, no dosage or medical advice. Prefer organ, "
    "department and specialty words over literal symptom words: a signboard "
    "reads 'Heart Institute', never 'chest pain'."
)


def generate_search_keywords(symptoms: str) -> Dict[str, object]:
    """
    Ask the LLM for 5 name-plausible keywords for these symptoms.

    Returns ``{"keywords": [...], "source": "ai" | "fallback"}``. The
    fallback path is a normal result, not an error: the hospitals page must
    never dead-end because NIM is rate-limited.
    """
    symptoms = (symptoms or "").strip()

    api_key = os.getenv("NVIDIA_NIM_API_KEY")
    if api_key and symptoms:
        try:
            # Imported lazily: this module is imported by app.api.hospitals at
            # startup, and the retriever pulls in pdfplumber.
            from app.api.hybrid_first_aid_retriever import nim_generate_json

            result = nim_generate_json(
                api_key=api_key,
                system_prompt=_KEYWORD_SYSTEM_PROMPT,
                user_message=f"PATIENT SYMPTOMS: {symptoms}",
                expect_key="keywords",
                per_model_timeout=8.0,
                max_retries=1,
            )
            if isinstance(result, dict):
                keywords = _clean_keywords(result.get("keywords"))
                if keywords:
                    return {
                        "keywords": _pad(keywords),
                        "source": "ai",
                    }
        except Exception:
            pass

    return {"keywords": fallback_keywords(symptoms), "source": "fallback"}


def _pad(keywords: List[str]) -> List[str]:
    """Guarantee KEYWORD_COUNT entries for callers that expect exactly 5."""
    seen = {keyword.lower() for keyword in keywords}
    for keyword in _GENERAL:
        if len(keywords) >= KEYWORD_COUNT:
            break
        if keyword.lower() not in seen:
            seen.add(keyword.lower())
            keywords.append(keyword)
    return keywords[:KEYWORD_COUNT]


# ---------------------------------------------------------
# 2. Keyword search
# ---------------------------------------------------------

def normalize_keywords(keywords: Sequence[str] | str | None) -> List[str]:
    """Split/normalise a keyword list and always append Multispeciality."""
    if isinstance(keywords, str):
        keywords = keywords.split(",")

    cleaned = _clean_keywords(list(keywords or []))

    if not any(_normalize(k) == _normalize(MULTISPECIALITY_KEYWORD) for k in cleaned):
        cleaned.append(MULTISPECIALITY_KEYWORD)

    return cleaned


def _sql_pattern(keyword: str) -> str:
    """
    Word-separated LIKE pattern: "multi speciality" -> `%multi%speciality%`.

    `%` between words also bridges `_`, `-`, `,` and newlines, so the SQL
    pre-filter stays a superset of the stricter word-start match Python runs
    on the same rows.
    """
    parts = _normalize(keyword).split()
    return "%" + "%".join(parts) + "%" if parts else "%"


def _match_expression(keywords: Sequence[str]):
    clauses = []
    for keyword in keywords:
        if _normalize(keyword) == _normalize(MULTISPECIALITY_KEYWORD):
            clauses.append(
                or_(*[column.ilike(_MULTISPECIALITY_SQL_PATTERN)
                      for column in _MATCH_COLUMNS])
            )
        else:
            pattern = _sql_pattern(keyword)
            clauses.append(
                or_(*[column.ilike(pattern) for column in _MATCH_COLUMNS])
            )
    return or_(*clauses)


def _matched_keywords(keywords: Sequence[str], hospital: Hospital) -> List[str]:
    """Which of the requested keywords actually hit this row (name first)."""
    name = _normalize(hospital.name)
    tagged = _normalize(
        " ".join(
            str(value or "")
            for value in (
                hospital.specialties,
                hospital.facilities,
                hospital.category,
                hospital.care_type,
                hospital.discipline,
            )
        )
    )

    matched: List[str] = []
    for keyword in keywords:
        normalized = _normalize(keyword)
        if not normalized:
            continue
        if normalized == _normalize(MULTISPECIALITY_KEYWORD):
            hit = bool(_MULTISPECIALITY_RE.search(name) or _MULTISPECIALITY_RE.search(tagged))
        else:
            rx = _keyword_regex(keyword)
            hit = bool(rx.search(name) or rx.search(tagged))
        if hit:
            matched.append(keyword)
    return matched


def search_by_keywords(
    db: Session,
    keywords: Sequence[str] | str,
    latitude: float,
    longitude: float,
    radius_km: Optional[float] = 100.0,
    limit: int = 50,
) -> List[Tuple[Hospital, float, List[str]]]:
    """
    Hospitals whose name/specialties contain any keyword, nearest first.

    Returns ``[(hospital, distance_km, matched_keywords), ...]`` sorted
    distance low -> high. When the radius hides every match the search is
    retried nationwide -- a keyword that means nothing within 100 km should
    still find the nearest matching hospital rather than an empty page.
    """
    normalized = normalize_keywords(keywords)
    if not _normalize(" ".join(normalized)):
        return []

    matches = _search_once(db, normalized, latitude, longitude, radius_km, limit)

    if not matches and radius_km is not None:
        matches = _search_once(db, normalized, latitude, longitude, None, limit)

    return matches


def _search_once(
    db: Session,
    keywords: Sequence[str],
    latitude: float,
    longitude: float,
    radius_km: Optional[float],
    limit: int,
) -> List[Tuple[Hospital, float, List[str]]]:
    query = db.query(Hospital).filter(_match_expression(keywords))

    if radius_km is not None:
        min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_km)
        query = query.filter(
            Hospital.latitude >= min_lat,
            Hospital.latitude <= max_lat,
            Hospital.longitude >= min_lon,
            Hospital.longitude <= max_lon,
        )

    scored: List[Tuple[Hospital, float, List[str]]] = []
    for hospital in query.all():
        matched = _matched_keywords(keywords, hospital)
        if not matched:
            # SQL matched on a substring mid-word; Python decided it is not
            # a real keyword hit (e.g. "ent" inside "Centre").
            continue

        distance = haversine_km(
            latitude, longitude, hospital.latitude, hospital.longitude
        )
        if radius_km is not None and distance > radius_km:
            continue

        scored.append((hospital, distance, matched))

    scored.sort(key=lambda row: row[1])
    return scored[:limit]


# ---------------------------------------------------------
# 3. Pincode search
# ---------------------------------------------------------

_NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
_reverse_cache: Dict[Tuple[float, float], Optional[str]] = {}
_reverse_cache_lock = threading.Lock()


def clean_pincode(value: object) -> Optional[str]:
    """Indian pincodes are 6 digits; accept any 4-8 digit postal code."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if 4 <= len(digits) <= 8:
        return digits
    return None


def _reverse_geocode_pincode(
    latitude: float,
    longitude: float,
    timeout: float = 4.0,
) -> Optional[str]:
    """Lat/long -> pincode via Nominatim, memoised at ~11 m precision."""
    key = (round(latitude, 4), round(longitude, 4))
    with _reverse_cache_lock:
        if key in _reverse_cache:
            return _reverse_cache[key]

    pincode: Optional[str] = None
    try:
        response = requests.get(
            _NOMINATIM_REVERSE_URL,
            params={
                "format": "jsonv2",
                "lat": latitude,
                "lon": longitude,
                "zoom": 18,
                "addressdetails": 1,
            },
            headers={"User-Agent": "MedTour-Navigator/2.0 (pincode lookup)"},
            timeout=timeout,
        )
        if response.ok:
            address = response.json().get("address") or {}
            pincode = clean_pincode(address.get("postcode"))
    except Exception:
        pincode = None

    with _reverse_cache_lock:
        _reverse_cache[key] = pincode
    return pincode


def nearest_directory_pincode(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float = 25.0,
) -> Optional[str]:
    """
    Offline fallback: the pincode of the closest facility in the directory.

    Used when the reverse geocoder is unreachable, and to recover a pincode
    for coordinates Nominatim only knows as a river or a highway.
    """
    min_lat, max_lat, min_lon, max_lon = bounding_box(latitude, longitude, radius_km)

    best_pin: Optional[str] = None
    best_distance = float("inf")

    rows = (
        db.query(Hospital)
        .filter(
            Hospital.latitude >= min_lat,
            Hospital.latitude <= max_lat,
            Hospital.longitude >= min_lon,
            Hospital.longitude <= max_lon,
        )
        .all()
    )

    for hospital in rows:
        pincode = clean_pincode(hospital.pincode)
        if not pincode:
            continue
        distance = haversine_km(
            latitude, longitude, hospital.latitude, hospital.longitude
        )
        if distance <= radius_km and distance < best_distance:
            best_distance = distance
            best_pin = pincode

    return best_pin


def resolve_pincode(
    db: Session,
    latitude: float,
    longitude: float,
) -> Tuple[Optional[str], str]:
    """Lat/long -> (pincode, source). Source is nominatim | directory | none."""
    pincode = _reverse_geocode_pincode(latitude, longitude)
    if pincode:
        return pincode, "nominatim"

    pincode = nearest_directory_pincode(db, latitude, longitude)
    if pincode:
        return pincode, "directory"

    return None, "none"


def search_by_pincode(
    db: Session,
    pincode: str,
    latitude: float,
    longitude: float,
    limit: int = 50,
) -> List[Tuple[Hospital, float]]:
    """
    Hospitals registered to `pincode`, distance from the caller low -> high.

    The distance is always measured from the caller's coordinates, so a
    pincode result is directly comparable with the nearby list.
    """
    cleaned = clean_pincode(pincode)
    if not cleaned:
        return []

    rows = (
        db.query(Hospital)
        .filter(func.replace(Hospital.pincode, " ", "") == cleaned)
        .all()
    )

    scored = [
        (
            hospital,
            haversine_km(latitude, longitude, hospital.latitude, hospital.longitude),
        )
        for hospital in rows
    ]
    scored.sort(key=lambda row: row[1])
    return scored[:limit]
