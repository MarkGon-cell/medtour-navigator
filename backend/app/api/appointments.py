"""
Appointment booking.

There are no patient accounts in this system — only doctors. A booking is
created from a docked `.mtr` medical profile (the UI disables scheduling when
no `.mtr` is signed in), and the server mints the unique appointment id that
the doctor portal, the QR scan and the claim PDF all key on.

This router deliberately holds nothing but the create endpoint. The old
JWT-gated per-user routes, and the check-in / start-consultation pair that fed
the waiting-time predictor, are gone: visit lifecycle and clinical detail live
on the patient's device and in their `.mtr`, not in PostgreSQL.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.doctor import _format_appointment
from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.hospital import Hospital
from app.schemas.appointment import AppointmentCreate, AppointmentResponse
from app.services.appointment_code import client_ip, generate_appointment_code


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


@router.post("", response_model=AppointmentResponse)
def create_appointment(
    request: AppointmentCreate,
    http_request: Request,
    db: Session = Depends(get_db),
):
    """
    Book an appointment.

    Stores only what the portal has to display: who, why, where, when, and
    the unique id. No clinical detail is accepted here and none is written —
    the diagnosis and prescription are entered later by the doctor and travel
    to the patient inside the QR, never through this table.
    """
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == request.hospital_id)
        .first()
    )

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    patient_name = (request.patient_name or "").strip()
    if not patient_name:
        raise HTTPException(
            status_code=400,
            detail="Patient name is required to book an appointment.",
        )

    reason = (request.reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail="Reason for the visit is required.",
        )

    def _taken(code: str) -> bool:
        return (
            db.query(Appointment.id)
            .filter(Appointment.appointment_code == code)
            .first()
            is not None
        )

    # Derived from the booking itself (time + patient + hospital + device) so
    # the id is unique by construction rather than by luck.
    appointment_code = generate_appointment_code(
        appointment_time=request.appointment_time,
        patient_name=patient_name,
        hospital_name=hospital.name or "",
        origin=client_ip(http_request),
        taken=_taken,
    )

    appointment = Appointment(
        appointment_code=appointment_code,
        patient_name=patient_name,
        reason=reason,
        hospital_id=hospital.id,
        hospital_name=hospital.name,
        department=request.department,
        appointment_time=request.appointment_time,
        status="upcoming",
        is_completed=False,
        is_verified=False,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return _format_appointment(appointment)
