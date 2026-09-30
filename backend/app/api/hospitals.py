from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.models.hospital_availability import HospitalAvailability
from app.database.database import get_db
from app.models.hospital import Hospital
from app.schemas.hospital import HospitalCreate, HospitalResponse
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import or_

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospitals"]
)


@router.post("/", response_model=HospitalResponse)
def create_hospital(
    hospital: HospitalCreate,
    db: Session = Depends(get_db)
):
    new_hospital = Hospital(**hospital.model_dump())

    db.add(new_hospital)
    db.commit()
    db.refresh(new_hospital)

    return new_hospital


@router.get("/", response_model=list[HospitalResponse])
def get_hospitals(
    db: Session = Depends(get_db)
):
    hospitals = db.query(Hospital).all()

    return hospitals

@router.get("/nearby")
def get_nearby_hospitals(
    latitude: float,
    longitude: float,
    radius_km: float = Query(
        10,
        ge=1,
        le=50
    ),
    specialty: str | None = None,
    emergency: bool = False,
    db: Session = Depends(get_db),
):
    hospitals = db.query(Hospital).all()

    nearby_hospitals = []

    R = 6371.0

    requested_specialty = (
        specialty.strip().lower()
        if specialty
        else None
    )

    specialty_aliases = {
        "cardiology": [
            "cardiology",
            "cardiologist",
            "cardiac",
            "heart",
        ],

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

        "neurology": [
            "neurology",
            "neurologist",
            "neuro",
        ],

        "oncology": [
            "oncology",
            "oncologist",
            "cancer",
        ],

        "pulmonology": [
            "pulmonology",
            "pulmonologist",
            "respiratory",
            "chest",
        ],
    }

    for hospital in hospitals:

        # -----------------------------------------
        # Distance calculation
        # -----------------------------------------

        lat1 = radians(latitude)
        lat2 = radians(
            hospital.latitude
        )

        delta_lat = radians(
            hospital.latitude - latitude
        )

        delta_lon = radians(
            hospital.longitude - longitude
        )

        a = (
            sin(delta_lat / 2) ** 2
            +
            cos(lat1)
            *
            cos(lat2)
            *
            sin(delta_lon / 2) ** 2
        )

        c = 2 * atan2(
            sqrt(a),
            sqrt(1 - a)
        )

        distance = R * c

        # -----------------------------------------
        # Radius filter
        # -----------------------------------------

        if distance > radius_km:
            continue

        # -----------------------------------------
        # Emergency filter
        # -----------------------------------------

        if (
            emergency
            and not hospital.emergency_available
        ):
            continue

        # -----------------------------------------
        # Specialty filter
        # -----------------------------------------

        if requested_specialty:

            hospital_specialties = (
                hospital.specialties or ""
            ).lower()

            hospital_specialties = (
                hospital_specialties
                .replace("_", " ")
                .replace("-", " ")
            )

            keywords = specialty_aliases.get(
                requested_specialty,
                [requested_specialty]
            )

            specialty_match = any(
                keyword in hospital_specialties
                for keyword in keywords
            )

            if not specialty_match:
                continue

        # -----------------------------------------
        # Result
        # -----------------------------------------

        nearby_hospitals.append({
            "id": hospital.id,

            "name": hospital.name,

            "city": hospital.city,

            "state": hospital.state,

            "district": hospital.district,

            "address": hospital.address,

            "pincode": hospital.pincode,

            "latitude":
                hospital.latitude,

            "longitude":
                hospital.longitude,

            "specialties":
                hospital.specialties,

            "facilities":
                hospital.facilities,

            "emergency_available":
                hospital.emergency_available,

            "emergency_services":
                hospital.emergency_services,

            "ambulance_phone":
                hospital.ambulance_phone,

            "phone":
                hospital.phone,

            "website":
                hospital.website,

            "total_beds":
                hospital.total_beds,

            "tariff_range":
                hospital.tariff_range,

            "distance_km":
                round(distance, 2),
        })

    # -----------------------------------------
    # Sort nearest first
    # -----------------------------------------

    nearby_hospitals.sort(
        key=lambda hospital:
            hospital["distance_km"]
    )

    return nearby_hospitals

@router.get("/search")
def search_hospitals(
    q: str,
    db: Session = Depends(get_db),
):
    search_term = q.strip()

    if not search_term:
        return []

    # Split search into individual words
    words = search_term.lower().split()

    query = db.query(Hospital)

    # Every word must match at least one searchable field
    for word in words:
        pattern = f"%{word}%"

        query = query.filter(
            or_(
                Hospital.name.ilike(pattern),
                Hospital.city.ilike(pattern),
                Hospital.state.ilike(pattern),
                Hospital.district.ilike(pattern),
                Hospital.specialties.ilike(pattern),
                Hospital.facilities.ilike(pattern),
            )
        )

    hospitals = query.limit(50).all()

    return [
        {
            "id": hospital.id,
            "name": hospital.name,
            "city": hospital.city,
            "state": hospital.state,
            "district": hospital.district,
            "address": hospital.address,
            "pincode": hospital.pincode,
            "latitude": hospital.latitude,
            "longitude": hospital.longitude,
            "specialties": hospital.specialties,
            "facilities": hospital.facilities,
            "emergency_available": hospital.emergency_available,
            "phone": hospital.phone,
            "total_beds": hospital.total_beds,
            "tariff_range": hospital.tariff_range,
        }
        for hospital in hospitals
    ]

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
        raise HTTPException(
            status_code=404,
            detail="Hospital not found",
        )

    availability = (
        db.query(HospitalAvailability)
        .filter(
            HospitalAvailability.hospital_id == hospital_id
        )
        .order_by(
            HospitalAvailability.observed_at.desc()
        )
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
        raise HTTPException(
            status_code=404,
            detail="Hospital not found",
        )

    return {
        "id": hospital.id,

        # Basic information
        "name": hospital.name,
        "category": hospital.category,
        "care_type": hospital.care_type,
        "discipline": hospital.discipline,

        # Location
        "city": hospital.city,
        "state": hospital.state,
        "district": hospital.district,
        "subdistrict": hospital.subdistrict,
        "address": hospital.address,
        "pincode": hospital.pincode,
        "latitude": hospital.latitude,
        "longitude": hospital.longitude,

        # Medical information
        "specialties": hospital.specialties,
        "facilities": hospital.facilities,
        "miscellaneous_facilities": hospital.miscellaneous_facilities,

        # Emergency
        "emergency_available": hospital.emergency_available,
        "emergency_services": hospital.emergency_services,
        "emergency_phone": hospital.emergency_phone,
        "ambulance_phone": hospital.ambulance_phone,
        "bloodbank_phone": hospital.bloodbank_phone,

        # Contact
        "phone": hospital.phone,
        "mobile": hospital.mobile,
        "tollfree": hospital.tollfree,
        "helpline": hospital.helpline,
        "website": hospital.website,
        "email": hospital.email,

        # Capacity
        "total_beds": hospital.total_beds,
        "private_wards": hospital.private_wards,
        "economically_weaker_beds": hospital.economically_weaker_beds,

        # Staff
        "doctors": hospital.doctors,
        "medical_consultants": hospital.medical_consultants,

        # Other
        "established_year": hospital.established_year,
        "accreditation": hospital.accreditation,
        "registration_number": hospital.registration_number,
        "empanelment": hospital.empanelment,
        "tariff_range": hospital.tariff_range,
    }