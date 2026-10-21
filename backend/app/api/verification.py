"""
Public claim verification — the destination of the QR printed on the
mediclaim PDF, and of the link beside it.

Both resolve to `{base}/verificationStatus?aid={appointment_code}`, so
scanning and tapping land on exactly the same answer: the operating doctor's
NMC verification status, the hospital, the patient, and a verified badge.

Deliberately unauthenticated. Whoever holds the PDF can check it is genuine,
which is the whole point of putting a verification QR on a claim document —
but it exposes only what the document already says, never the clinical detail,
which was never stored here in the first place.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.services.claim_pdf import verification_url


router = APIRouter(tags=["Claim Verification"])


@router.get("/verificationStatus")
def verification_status(aid: str, db: Session = Depends(get_db)):
    """
    Resolve an appointment id (`MT-XXXXXXXX`) to its verification status.

    Returns the facts needed to render a verification page — who operated,
    where, on whom, whether the claim was purchased, and a badge — plus the
    deterministic hash backing it. No diagnosis or prescription is returned:
    those never lived on this server.
    """
    code = (aid or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="An appointment id is required.")

    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == code)
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=f"No appointment found for id '{code}'.",
        )

    hospital = appointment.hospital

    doctor = None
    if appointment.doctor_name:
        doctor = (
            db.query(Doctor)
            .filter(Doctor.full_name == appointment.doctor_name)
            .order_by(Doctor.verified.desc(), Doctor.id.desc())
            .first()
        )

    # The appointment becomes verified once the patient pays the $15 claim generation fee
    # (or if the doctor's credentials are affirmatively verified).
    is_claim_verified = bool(appointment.is_verified)
    doctor_verified = bool(doctor.verified) if doctor else False
    overall_verified = is_claim_verified or doctor_verified

    return {
        "appointment_code": appointment.appointment_code,
        "is_verified": is_claim_verified,
        "is_completed": appointment.is_completed,
        "badge": "VERIFIED" if overall_verified else "PENDING VERIFICATION",
        "verified": overall_verified,
        "doctor": {
            "name": doctor.full_name if doctor else appointment.doctor_name,
            "reg_number": doctor.reg_number if doctor else None,
            "state_council": doctor.state_council if doctor else None,
            "qualification": doctor.qualification if doctor else None,
            "specialization": doctor.specialization if doctor else None,
            "verified": doctor_verified,
            "verified_at": doctor.verified_at if doctor else None,
        },
        "hospital": {
            "name": appointment.hospital_name
            or (hospital.name if hospital else None),
            "address": hospital.address if hospital else None,
            "city": hospital.city if hospital else None,
            "state": hospital.state if hospital else None,
            "phone": hospital.phone if hospital else None,
        },
        "patient": {
            "name": appointment.patient_name,
        },
        "visit": {
            "department": appointment.department,
            "appointment_time": appointment.appointment_time,
            "reason": appointment.reason,
            "status": appointment.status,
        },
        "verification_url": verification_url(appointment.appointment_code),
    }
