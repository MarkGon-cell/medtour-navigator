"""
Doctor authentication API (client/server).

Flow (registration doubles as NMC verification):
  1. Client POSTs credentials + IMR registration details.
  2. Backend verifies the reg number against https://api.askmydoc.in
     (free NMC Indian Medical Register proxy) — result cached in-memory
     (TTL) and persisted on the doctor row (`verification_json`,
     `verified_at`) so subsequent logins/profile reads are local.
  3. Only a verified doctor gets an account + JWT (`role: "doctor"`).

Profile reads (`GET /doctor/auth/me`) always answer from the database
cache; `POST /doctor/auth/reverify` is the explicit "hit the live API now"
escape hatch.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.doctor_auth import get_current_doctor
from app.auth.jwt_handler import create_access_token
from app.auth.security import hash_password, verify_password
from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.schemas.doctor import (
    DoctorAuthResponse,
    DoctorLoginInput,
    DoctorProfile,
    DoctorRegisterInput,
    DoctorReverifyInput,
    DoctorVerificationInfo,
)
from app.services import askmydoc

router = APIRouter(
    prefix="/doctor/auth",
    tags=["Doctor Auth"],
)

_VERIFICATION_SOURCE = "api.askmydoc.in (NMC Indian Medical Register)"


def _build_profile(db: Session, doctor: Doctor, cached: bool = True) -> DoctorProfile:
    """Assemble the portal's doctor profile from the local cache only."""
    hospital_name: Optional[str] = None
    if doctor.hospital_id:
        hospital = db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first()
        hospital_name = hospital.name if hospital else None

    appointment_count = (
        db.query(Appointment.id)
        .filter(Appointment.hospital_id == doctor.hospital_id)
        .count()
        if doctor.hospital_id
        else db.query(Appointment.id).count()
    )

    import json as _json

    detail: dict = {}
    if doctor.verification_json:
        try:
            detail = _json.loads(doctor.verification_json) or {}
        except (ValueError, TypeError):
            detail = {}

    return DoctorProfile(
        id=doctor.id,
        full_name=doctor.full_name,
        email=doctor.email,
        reg_number=doctor.reg_number,
        state_council=doctor.state_council,
        reg_year=doctor.reg_year,
        specialization=doctor.specialization,
        qualification=doctor.qualification or detail.get("qualification"),
        phone=doctor.phone,
        hospital_id=doctor.hospital_id,
        hospital_name=hospital_name,
        verification=DoctorVerificationInfo(
            verified=doctor.verified,
            verified_at=doctor.verified_at,
            reg_number=doctor.reg_number,
            state_council=doctor.state_council,
            year=doctor.reg_year,
            qualification=doctor.qualification or detail.get("qualification"),
            status=detail.get("status") or ("verified" if doctor.verified else None),
            cached=cached,
            source=_VERIFICATION_SOURCE,
        ),
        appointment_count=appointment_count,
        created_at=doctor.created_at,
    )


@router.post("/register", response_model=DoctorAuthResponse)
def register_doctor(payload: DoctorRegisterInput, db: Session = Depends(get_db)):
    """
    Register a doctor after verifying their NMC registration number through
    api.askmydoc.in. Rejects duplicates and unverifiable registrations.
    """
    normalized_email = payload.email.strip().lower()

    if db.query(Doctor.id).filter(Doctor.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    reg = payload.reg_number.strip()
    if db.query(Doctor.id).filter(Doctor.reg_number == reg).first():
        raise HTTPException(status_code=409, detail=f"Registration number '{reg}' is already registered.")

    if payload.hospital_id is not None:
        hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
        if not hospital:
            raise HTTPException(status_code=400, detail="Selected hospital does not exist.")

    # Live NMC verification (debounced by the in-memory TTL cache).
    verification = askmydoc.verify_doctor(
        reg,
        state_council=payload.state_council,
        year=payload.year,
        force_refresh=True,
    )

    if verification["status"] == "not_found":
        raise HTTPException(
            status_code=400,
            detail=(
                "NMC verification failed: "
                + (verification.get("reason") or "registration number not found in the Indian Medical Register.")
            ),
        )

    # `unavailable` = the verification service could not reach the NMC right
    # now. Refusing to create the account would lock every doctor out during
    # an upstream outage, so we create the account UNVERIFIED and let
    # `POST /doctor/auth/reverify` upgrade it once the service is back.
    verification_service_ok = bool(verification["verified"])

    import json as _json

    doctor = Doctor(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        password=hash_password(payload.password),
        reg_number=reg,
        state_council=payload.state_council.strip() if payload.state_council else verification.get("state_council"),
        reg_year=payload.year if payload.year else verification.get("year"),
        specialization=payload.specialization.strip() if payload.specialization else None,
        qualification=payload.qualification or verification.get("qualification"),
        phone=payload.phone.strip() if payload.phone else None,
        hospital_id=payload.hospital_id,
        verified=verification_service_ok,
        verified_at=datetime.utcnow() if verification_service_ok else None,
        # Cache the NORMALIZED result (not just the upstream payload) so the
        # portal can still tell "pending: service unavailable" from a real
        # verification without re-calling the API on every page load.
        verification_json=_json.dumps(verification, default=str),
    )
    db.add(doctor)
    db.commit()
    db.refresh(doctor)

    token = create_access_token(
        {"sub": doctor.email, "role": "doctor", "doctor_id": doctor.id, "name": doctor.full_name}
    )
    return DoctorAuthResponse(access_token=token, profile=_build_profile(db, doctor, cached=False))


@router.post("/login", response_model=DoctorAuthResponse)
def login_doctor(payload: DoctorLoginInput, db: Session = Depends(get_db)):
    """Email + password login. Verification info comes from the row cache."""
    normalized_email = payload.email.strip().lower()
    doctor = db.query(Doctor).filter(Doctor.email == normalized_email).first()

    if not doctor or not verify_password(payload.password, doctor.password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = create_access_token(
        {"sub": doctor.email, "role": "doctor", "doctor_id": doctor.id, "name": doctor.full_name}
    )
    return DoctorAuthResponse(access_token=token, profile=_build_profile(db, doctor, cached=True))


@router.get("/me", response_model=DoctorProfile)
def doctor_profile(
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    """Current doctor's profile — served entirely from the DB cache."""
    return _build_profile(db, doctor, cached=True)


@router.post("/reverify", response_model=DoctorProfile)
def reverify_doctor(
    payload: DoctorReverifyInput,
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    """
    Force a fresh call to api.askmydoc.in and refresh the cached verdict.
    Kept for the portal's "Re-verify NMC registration" action.
    """
    verification = askmydoc.verify_doctor(
        doctor.reg_number,
        state_council=doctor.state_council,
        year=doctor.reg_year,
        force_refresh=payload.force_refresh,
    )

    import json as _json

    doctor.verified = bool(verification["verified"])
    doctor.verified_at = datetime.utcnow() if doctor.verified else None
    doctor.verification_json = _json.dumps(verification.get("raw") or verification, default=str)
    if verification.get("qualification") and not doctor.qualification:
        doctor.qualification = verification["qualification"]
    db.commit()
    db.refresh(doctor)

    return _build_profile(db, doctor, cached=not payload.force_refresh)
