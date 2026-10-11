import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.database import get_db
from app.models.hospital import Hospital
from app.models.curated_hospital import CuratedHospital
from app.models.hospital_availability import HospitalAvailability
from app.models.user import User
from app.schemas.hospital import HospitalCreate, HospitalResponse
from app.services.geo import bounding_box, haversine_km  # noqa: F401 (re-exported)
from app.services import discovery, hospital_search

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospitals"],
)

# Writes to the verified directory are disabled unless an operator sets this
# key. Without it, POST /hospitals/ would let anyone inject rows into the
# directory that patients rely on. Note this gate does NOT apply to
# GET /hospitals/discover, which persists only facilities that are genuinely
# new after deduplication -- see app/services/discovery.py.
HOSPITAL_WRITE_KEY = os.getenv("HOSPITAL_WRITE_KEY")


# ---------------------------------------------------------
# Serialization
# ---------------------------------------------------------

def _is_general_or_multispeciality_facility(name: str = "", specialties: str = "", category: str = "", care_type: str = "") -> bool:
    """
    Checks if a facility has the profile of a General, Multi-Speciality,
    Super-Speciality, District, Civil, or Tertiary hospital with 24/7 acute stabilization capabilities.
    """
    text = f"{name} {specialties} {category} {care_type}".lower()
    positive_indicators = [
        "multi", "multispeciality", "multi-speciality", "multi speciality",
        "multispecialty", "multi-specialty", "multi specialty",
        "superspeciality", "super speciality", "super-speciality", "superspecialty",
        "general", "general hospital", "civil hospital", "district hospital",
        "tertiary", "trauma", "casualty", "government hospital",
        "govt hospital", "medical college", "acute care", "critical care",
        "emergency care", "mission hospital", "memorial hospital",
        "community health centre", "chc", "sub-district hospital"
    ]
    return any(k in text for k in positive_indicators)


def _is_disqualified_clinic_facility(name: str = "", specialties: str = "", category: str = "") -> bool:
    """
    Detects single-specialty niche clinics (eye, dental, skin, etc.) and small nursing homes
    that do not operate full-service 24/7 general emergency departments.
    """
    text = f"{name} {specialties} {category}".lower()
    # If explicitly multispeciality/trauma/general/civil/district, do not disqualify
    if any(k in text for k in [
        "multi", "general", "civil", "district", "trauma", "medical college",
        "superspeciality", "tertiary", "memorial"
    ]):
        return False
    disqualifiers = [
        "nursing home", "maternity", "maternity home", "maternity and nursing home",
        "eye", "ophthal", "dental", "dentist", "skin", "derma", "cosmetic",
        "urology", "physio", "ayurved", "homeo", "fertility", "ivf",
        "day care", "outpatient clinic", "dispensary", "polyclinic"
    ]
    return any(k in text for k in disqualifiers)


def _nearby_payload(
    hospital: Hospital,
    distance_km: float,
) -> dict:
    """Everything the emergency toolkit and facility cards need."""
    is_general_or_multi = _is_general_or_multispeciality_facility(
        name=hospital.name or "",
        specialties=hospital.specialties or "",
        category=hospital.category or "",
        care_type=hospital.care_type or "",
    )
    is_disqualified = _is_disqualified_clinic_facility(
        name=hospital.name or "",
        specialties=hospital.specialties or "",
        category=hospital.category or "",
    )

    return {
        "id": hospital.id,
        "name": hospital.name,
        "category": hospital.category,
        "care_type": hospital.care_type,
        "city": hospital.city,
        "state": hospital.state,
        "district": hospital.district,
        "address": hospital.address,
        "pincode": hospital.pincode,
        "latitude": hospital.latitude,
        "longitude": hospital.longitude,
        "specialties": hospital.specialties,
        "facilities": hospital.facilities,
        "is_general_or_multispeciality": is_general_or_multi,
        "is_disqualified_clinic": is_disqualified,
        # Emergency contact block. Note: coverage in the source directory is
        # poor (see docs/architecture.md) -- treat presence as a bonus, never
        # as proof that an emergency room exists.
        "emergency_available": hospital.emergency_available,
        "emergency_services": hospital.emergency_services,
        "emergency_phone": hospital.emergency_phone,
        "ambulance_phone": hospital.ambulance_phone,
        "bloodbank_phone": hospital.bloodbank_phone,
        # General contact
        "phone": hospital.phone,
        "mobile": hospital.mobile,
        "tollfree": hospital.tollfree,
        "helpline": hospital.helpline,
        "website": hospital.website,
        "total_beds": hospital.total_beds,
        "accreditation": hospital.accreditation,
        "registration_number": hospital.registration_number,
        "tariff_range": hospital.tariff_range,
        "distance_km": round(distance_km, 2),
    }


# ---------------------------------------------------------
# Directory writes
# ---------------------------------------------------------

@router.post("/", response_model=HospitalResponse)
def create_hospital(
    hospital: HospitalCreate,
    x_hospital_write_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if not HOSPITAL_WRITE_KEY:
        raise HTTPException(
            status_code=403,
            detail=(
                "Directory writes are disabled. Set HOSPITAL_WRITE_KEY to "
                "enable them."
            ),
        )

    if x_hospital_write_key != HOSPITAL_WRITE_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid directory write key.",
        )

    new_hospital = Hospital(**hospital.model_dump())

    db.add(new_hospital)
    db.commit()
    db.refresh(new_hospital)

    return new_hospital


# ---------------------------------------------------------
# Reads
# ---------------------------------------------------------

@router.get("/")
def get_hospitals(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Paginated directory listing.

    Previously this returned every row in the table (~30k) with no paging.
    """
    total = db.query(Hospital).count()

    hospitals = (
        db.query(Hospital)
        .order_by(Hospital.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_nearby_payload(h, 0.0) for h in hospitals],
    }


@router.get("/nearby")
def get_nearby_hospitals(
    latitude: float,
    longitude: float,
    radius_km: float = Query(10, ge=1, le=50),
    specialty: str | None = None,
    emergency: bool = False,
    sort: str = Query(
        "distance",
        pattern="^(distance|emergency)$",
        description=(
            "distance: nearest first (default). "
            "emergency: emergency-capable and reachable facilities first, "
            "then nearest."
        ),
    ),
    limit: int | None = Query(
        None,
        ge=1,
        le=200,
        description="Optional cap on returned rows, e.g. limit=3 for the SOS sheet.",
    ),
    db: Session = Depends(get_db),
):
    """
    Facilities near a point.

    Two-stage query: a bounding-box predicate on the indexed lat/lon columns,
    then an exact haversine over that candidate set. This replaces a full
    table scan that materialised every row in Python on each request.

    `emergency=True` ranks emergency-capable facilities first rather than
    discarding the rest: the source directory marks only a handful of
    facilities as emergency-capable, so filtering would return an empty list
    almost everywhere in India. Per-row `emergency_available` stays truthful
    so callers can badge accurately.
    """
    min_lat, max_lat, min_lon, max_lon = bounding_box(
        latitude, longitude, radius_km
    )

    candidates = (
        db.query(Hospital)
        .filter(
            Hospital.latitude >= min_lat,
            Hospital.latitude <= max_lat,
            Hospital.longitude >= min_lon,
            Hospital.longitude <= max_lon,
        )
        .all()
    )

    # When emergency mode is requested or candidate pool is sparse, supplement
    # candidates dynamically via Google Places + Overpass + Geoapify.
    has_gen_multi = any(
        _is_general_or_multispeciality_facility(h.name, h.specialties or "", h.category or "", h.care_type or "")
        for h in candidates
    )
    if (emergency or sort == "emergency" or len(candidates) < 3 or not has_gen_multi):
        try:
            discovered = discovery.discover(
                db, latitude, longitude, radius_km,
                persist=True, limit=discovery.MAX_RESULTS, fast=True,
            )
            # Reload updated candidate rows in bbox
            candidates = (
                db.query(Hospital)
                .filter(
                    Hospital.latitude >= min_lat,
                    Hospital.latitude <= max_lat,
                    Hospital.longitude >= min_lon,
                    Hospital.longitude <= max_lon,
                )
                .all()
            )
        except Exception as exc:
            pass

    requested_specialty = specialty.strip().lower() if specialty else None

    specialty_aliases = {
        "cardiology": ["cardiology", "cardiologist", "cardiac", "heart"],
        "orthopedic": [
            "orthopedic",
            "orthopaedic",
            "orthopedics",
            "orthopaedics",
            "bone",
            "joint",
        ],
        "general medicine": [
            "general medicine",
            "internal medicine",
            "physician",
        ],
        "pediatrics": [
            "pediatric",
            "paediatric",
            "pediatrics",
            "paediatrics",
            "children",
        ],
        "gynecology": [
            "gynecology",
            "gynaecology",
            "gynecologist",
            "gynaecologist",
            "women",
        ],
        "neurology": ["neurology", "neurologist", "neuro"],
        "oncology": ["oncology", "oncologist", "cancer"],
        "pulmonology": ["pulmonology", "pulmonologist", "respiratory", "chest"],
    }

    results: list[dict] = []

    for hospital in candidates:
        distance = haversine_km(
            latitude,
            longitude,
            hospital.latitude,
            hospital.longitude,
        )

        if distance > radius_km:
            continue

        # Specialty filter
        if requested_specialty:
            haystack = (hospital.specialties or "").lower()
            haystack = haystack.replace("_", " ").replace("-", " ")

            keywords = specialty_aliases.get(
                requested_specialty,
                [requested_specialty],
            )

            if not any(keyword in haystack for keyword in keywords):
                continue

        payload = _nearby_payload(hospital, distance)

        # Emergency-contact coverage is sparse in this dataset; expose a
        # per-row hint so callers can distinguish "flagged as emergency"
        # from "unknown".
        payload["has_emergency_phone"] = bool(
            _looks_like_a_number(hospital.emergency_phone)
            or _looks_like_a_number(hospital.ambulance_phone)
            or _looks_like_a_number(hospital.phone)
        )

        results.append(payload)

    # -----------------------------------------------------
    # Ranking
    # -----------------------------------------------------
    if sort == "emergency" or emergency:
        # Prioritize General or Multi-Speciality hospitals for SOS/Emergency over single-specialty clinics
        results.sort(
            key=lambda row: (
                0 if row.get("emergency_available") else 1,
                1 if row.get("is_disqualified_clinic") else 0,
                0 if row.get("is_general_or_multispeciality") else 1,
                0 if row.get("has_emergency_phone") else 1,
                row["distance_km"],
            )
        )
    else:
        results.sort(key=lambda row: row["distance_km"])

    if limit is not None:
        results = results[:limit]

    return results


def _looks_like_a_number(value: str | None) -> bool:
    """True when a directory field holds something dialable, not a '0' placeholder."""
    if not value:
        return False
    digits = "".join(ch for ch in value if ch.isdigit())
    return len(digits) >= 6


@router.get("/discover")
def discover_facilities(
    latitude: float,
    longitude: float,
    radius_km: float = Query(10, ge=1, le=50),
    limit: int = Query(50, ge=1, le=200),
    persist: bool = Query(
        True,
        description=(
            "Store facilities that are not already in the directory. "
            "Set false for a read-only probe."
        ),
    ),
    db: Session = Depends(get_db),
):
    """
    Search Overpass + Geoapify together with the local directory, and persist
    only facilities that are genuinely new.

    Use this when you want the combined, network-backed view. Use
    `GET /hospitals/nearby` for the local-only path: it touches no external
    service, so it stays fast and works with no network.

    Guarantees:
      * Nothing already in the directory is inserted twice.
      * Existing rows are never overwritten -- this endpoint only adds.
      * If every external provider fails, you still get local results with
        `degraded: true` and a per-provider status in `sources`, rather than
        an error. An emergency flow must not break because a mirror is down.

    The response wraps `results` rather than returning a bare array, because
    the caller needs to distinguish "no hospitals here" from "the providers
    were unreachable".
    """
    return discovery.discover(
        db,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        persist=persist,
        limit=limit,
    )


@router.get("/search")
def search_hospitals(
    q: str,
    db: Session = Depends(get_db),
):
    search_term = q.strip()

    if not search_term:
        return []

    words = search_term.lower().split()

    query = db.query(Hospital)

    for word in words:
        pattern = f"%{word}%"
        query = query.filter(
            Hospital.name.ilike(pattern)
            | Hospital.city.ilike(pattern)
            | Hospital.state.ilike(pattern)
            | Hospital.district.ilike(pattern)
            | Hospital.specialties.ilike(pattern)
            | Hospital.facilities.ilike(pattern)
        )

    hospitals = query.limit(50).all()

    return [_nearby_payload(h, 0.0) for h in hospitals]


# ---------------------------------------------------------
# Symptom-keyword search (AI) & pincode search
# ---------------------------------------------------------

class SymptomKeywordRequest(BaseModel):
    symptoms: str = Field(..., min_length=3, max_length=500)


@router.post("/keywords")
def build_search_keywords(
    req: SymptomKeywordRequest,
):
    """
    Step 1 of the symptom search: ask the AI for the 5 keywords most likely
    to appear in a hospital's *name* for these symptoms ("Heart", "Cardiac",
    "Cardiology", ...).

    `source: "fallback"` is a normal answer, not an error: it means NIM was
    unreachable and the deterministic symptom table replied instead, so the
    UI can still run the search. `extra_keywords` always carries
    Multispeciality, which the caller must search alongside the 5.
    """
    result = hospital_search.generate_search_keywords(req.symptoms)

    return {
        "symptoms": req.symptoms.strip(),
        "keywords": result["keywords"],
        "extra_keywords": [hospital_search.MULTISPECIALITY_KEYWORD],
        "source": result["source"],
    }


@router.get("/by-keywords")
def get_hospitals_by_keywords(
    latitude: float,
    longitude: float,
    keywords: str = Query(
        ...,
        min_length=1,
        max_length=300,
        description=(
            "Comma-separated keywords, typically the `keywords` + "
            "`extra_keywords` returned by POST /hospitals/keywords."
        ),
    ),
    radius_km: float = Query(
        100,
        ge=1,
        le=1000,
        description="Search envelope around the caller. Zero hits inside it retry nationwide.",
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Step 2: index the directory for those keywords and return the matching
    facilities ordered distance low -> high from the caller's coordinates.

    A keyword match is word-start based, so "ent" finds the ENT block but
    never "Centre"; every row reports which keywords it matched in
    `matched_keywords`.
    """
    matches = hospital_search.search_by_keywords(
        db,
        keywords=keywords,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )

    payload = []
    for hospital, distance, matched in matches:
        row = _nearby_payload(hospital, distance)
        row["matched_keywords"] = matched
        payload.append(row)

    return payload


@router.get("/by-pincode")
def get_hospitals_by_pincode(
    latitude: float,
    longitude: float,
    pincode: str | None = Query(
        None,
        description="Optional override. Omit to derive the pincode from latitude/longitude.",
    ),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    Pincode search: resolve the caller's pincode from their coordinates
    (reverse geocoder, falling back to the nearest facility in the
    directory), list that pincode's hospitals and measure each one from the
    caller -- nearest first, exactly like `/nearby`.

    The response wraps `items` because the caller needs the resolved
    `pincode` it did not know, plus `source` so the UI can say where it came
    from. `pincode: null` means nothing could be derived.
    """
    source = "provided"
    resolved = hospital_search.clean_pincode(pincode) if pincode else None

    if not resolved:
        resolved, source = hospital_search.resolve_pincode(db, latitude, longitude)

    if not resolved:
        return {"pincode": None, "source": "none", "items": []}

    matches = hospital_search.search_by_pincode(
        db, resolved, latitude, longitude, limit
    )

    # The reverse geocoder can name a pincode the directory has never heard
    # of (fresh allocation, neighbouring district). Fall back to the nearest
    # facility's pincode rather than showing an empty page.
    if not matches and source == "nominatim":
        alternative = hospital_search.nearest_directory_pincode(
            db, latitude, longitude
        )
        if alternative and alternative != resolved:
            matches = hospital_search.search_by_pincode(
                db, alternative, latitude, longitude, limit
            )
            if matches:
                resolved, source = alternative, "directory"

    return {
        "pincode": resolved,
        "source": source,
        "items": [
            _nearby_payload(hospital, distance)
            for hospital, distance in matches
        ],
    }


@router.get("/{hospital_id}/availability")
def get_hospital_availability(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == hospital_id)
        .first()
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    availability = (
        db.query(HospitalAvailability)
        .filter(HospitalAvailability.hospital_id == hospital_id)
        .order_by(HospitalAvailability.observed_at.desc())
        .first()
    )

    if not availability:
        return {
            "hospital_id": hospital_id,
            "availability_available": False,
            "message": "No availability data is currently available.",
        }

    return {
        "hospital_id": hospital_id,
        "availability_available": True,
        "available_general_beds": availability.available_general_beds,
        "available_icu_beds": availability.available_icu_beds,
        "available_emergency_beds": availability.available_emergency_beds,
        "emergency_status": availability.emergency_status,
        "source_type": availability.source_type,
        "source_url": availability.source_url,
        "observed_at": availability.observed_at,
        "expires_at": availability.expires_at,
        "confidence": availability.confidence,
    }


@router.get("/curated")
def get_curated_hospitals(
    city: str | None = Query(default=None),
    state: str | None = Query(default=None),
    ai_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Returns facilities from the new curated_hospitals table with AI-enriched columns:
    speciality, tier, rating, services, amenities, phone, emergency_phone, website.
    """
    query = db.query(CuratedHospital)
    if city:
        query = query.filter(CuratedHospital.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(CuratedHospital.state.ilike(f"%{state}%"))
    if ai_only:
        query = query.filter(CuratedHospital.ai_enriched == True)

    results = query.order_by(CuratedHospital.ai_enriched.desc(), CuratedHospital.rating.desc().nullslast()).limit(limit).all()

    return [
        {
            "id": h.id,
            "name": h.name,
            "address": h.address,
            "city": h.city,
            "state": h.state,
            "district": h.district,
            "pincode": h.pincode,
            "latitude": h.latitude,
            "longitude": h.longitude,
            "phone": h.phone,
            "emergency_phone": h.emergency_phone,
            "website": h.website,
            "emergency_available": h.emergency_available,
            "speciality": h.speciality,
            "tier": h.tier,
            "rating": h.rating,
            "services": h.services,
            "amenities": h.amenities,
            "ai_enriched": h.ai_enriched,
            "ai_enriched_at": h.ai_enriched_at,
        }
        for h in results
    ]


@router.get("/{hospital_id}")
def get_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == hospital_id)
        .first()
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    return {
        "id": hospital.id,
        "name": hospital.name,
        "category": hospital.category,
        "care_type": hospital.care_type,
        "discipline": hospital.discipline,
        "city": hospital.city,
        "state": hospital.state,
        "district": hospital.district,
        "subdistrict": hospital.subdistrict,
        "address": hospital.address,
        "pincode": hospital.pincode,
        "latitude": hospital.latitude,
        "longitude": hospital.longitude,
        "specialties": hospital.specialties,
        "facilities": hospital.facilities,
        "miscellaneous_facilities": hospital.miscellaneous_facilities,
        "emergency_available": hospital.emergency_available,
        "emergency_services": hospital.emergency_services,
        "emergency_phone": hospital.emergency_phone,
        "ambulance_phone": hospital.ambulance_phone,
        "bloodbank_phone": hospital.bloodbank_phone,
        "phone": hospital.phone,
        "mobile": hospital.mobile,
        "tollfree": hospital.tollfree,
        "helpline": hospital.helpline,
        "website": hospital.website,
        "email": hospital.email,
        "total_beds": hospital.total_beds,
        "private_wards": hospital.private_wards,
        "economically_weaker_beds": hospital.economically_weaker_beds,
        "doctors": hospital.doctors,
        "medical_consultants": hospital.medical_consultants,
        "established_year": hospital.established_year,
        "accreditation": hospital.accreditation,
        "registration_number": hospital.registration_number,
        "empanelment": hospital.empanelment,
        "tariff_range": hospital.tariff_range,
    }
