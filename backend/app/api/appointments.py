"""
DEPRECATED ROUTER — mounted, but no longer the source of truth for visits.

docs/architecture.md section 6 and docs/FRONTEND.md section 5 make appointments
guest-local: the ledger lives in localStorage under the guest's device, is
readable with no token, and never redirects to /login. These eight JWT-gated
routes are retained because:

  * a signed-in user's older records live here, and
  * `/check-in` and `/start-consultation` still write `HospitalWaitingObservation`,
    which is the training data behind `/waiting-time/predict` — an in-scope
    feature (walk-in expectation setting).

No new appointment features. Delete once the frontend stops syncing.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.hospital import Hospital
from app.models.user import User
from app.models.hospital_waiting_observation import (
    HospitalWaitingObservation,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentStatusUpdate,
)
from app.auth.dependencies import get_current_user
from app.models.hospital_queue_status import HospitalQueueStatus


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


def _format_appointment(app: Appointment, user: Optional[User] = None) -> dict:
    return {
        "id": app.id,
        "user_id": app.user_id,
        "hospital_id": app.hospital_id,
        "department": app.department,
        "appointment_time": app.appointment_time,
        "status": app.status,
        "symptoms": app.symptoms,
        "is_emergency": app.is_emergency,
        "check_in_time": app.check_in_time,
        "consultation_start_time": app.consultation_start_time,
        "created_at": app.created_at,
        "hospital": app.hospital,
        "user_name": app.user.full_name if app.user else (user.full_name if user else None),
        "user_email": app.user.email if app.user else (user.email if user else None),
    }


@router.post("", response_model=AppointmentResponse)
def create_appointment(
    request: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    hospital = (
        db.query(Hospital)
        .filter(Hospital.id == request.hospital_id)
        .first()
    )

    if not hospital:
        raise HTTPException(
            status_code=404,
            detail="Hospital not found",
        )

    appointment = Appointment(
        user_id=current_user.id,
        hospital_id=request.hospital_id,
        department=request.department,
        appointment_time=request.appointment_time,
        symptoms=request.symptoms,
        is_emergency=request.is_emergency,
        status="upcoming",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return _format_appointment(appointment, current_user)


@router.get("", response_model=list[AppointmentResponse])
def get_my_appointments(
    status: Optional[str] = Query(None, description="Filter by status: upcoming, completed, cancelled, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Appointment)
        .filter(Appointment.user_id == current_user.id)
    )

    if status:
        status_clean = status.strip().lower()
        if status_clean == "upcoming":
            query = query.filter(
                Appointment.status.in_(["upcoming", "booked", "checked_in", "in_consultation"])
            )
        elif status_clean == "completed":
            query = query.filter(Appointment.status == "completed")
        elif status_clean == "cancelled":
            query = query.filter(Appointment.status == "cancelled")

    appointments = query.order_by(Appointment.appointment_time.desc()).all()
    return [_format_appointment(app, current_user) for app in appointments]


@router.get("/{appointment_id}", response_model=AppointmentResponse)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return _format_appointment(appointment, current_user)


@router.patch("/{appointment_id}/cancel", response_model=AppointmentResponse)
@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse)
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status == "completed":
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel an already completed appointment",
        )

    appointment.status = "cancelled"
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    return _format_appointment(appointment, current_user)


@router.patch("/{appointment_id}/status", response_model=AppointmentResponse)
def update_status(
    appointment_id: int,
    req: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    valid_statuses = ["upcoming", "completed", "cancelled", "checked_in", "booked"]
    status_lower = req.status.strip().lower()
    if status_lower not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Must be one of: {valid_statuses}",
        )

    appointment.status = status_lower
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    return _format_appointment(appointment, current_user)


@router.delete("/{appointment_id}")
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.delete(appointment)
    db.commit()
    return {"success": True, "message": "Appointment deleted successfully"}


@router.post("/{appointment_id}/check-in")
def check_in(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    if appointment.check_in_time is not None:
        raise HTTPException(
            status_code=400,
            detail="Appointment already checked in",
        )

    appointment.check_in_time = datetime.utcnow()
    appointment.status = "checked_in"

    db.commit()
    db.refresh(appointment)

    # Automatically calculate current queue
    queue_query = (
        db.query(Appointment)
        .filter(
            Appointment.hospital_id == appointment.hospital_id,
            Appointment.status.in_(["checked_in", "in_consultation"]),
        )
    )

    if appointment.department:
        queue_query = queue_query.filter(
            Appointment.department == appointment.department
        )

    waiting_patients = queue_query.count()
    emergency_patients = (
        queue_query.filter(Appointment.is_emergency == True).count()
    )

    # Get latest available doctor count
    latest_queue = (
        db.query(HospitalQueueStatus)
        .filter(HospitalQueueStatus.hospital_id == appointment.hospital_id)
    )

    if appointment.department:
        latest_queue = latest_queue.filter(
            HospitalQueueStatus.department == appointment.department
        )

    latest_queue = (
        latest_queue.order_by(HospitalQueueStatus.updated_at.desc()).first()
    )

    available_doctors = (
        latest_queue.available_doctors if latest_queue else None
    )

    queue_snapshot = HospitalQueueStatus(
        hospital_id=appointment.hospital_id,
        department=appointment.department,
        queue_size=waiting_patients,
        emergency_cases=emergency_patients,
        available_doctors=(
            available_doctors if available_doctors is not None else 0
        ),
        updated_at=datetime.utcnow(),
        source="medtour_appointment",
    )

    db.add(queue_snapshot)
    db.commit()
    db.refresh(queue_snapshot)

    return {
        "success": True,
        "appointment_id": appointment.id,
        "status": appointment.status,
        "check_in_time": appointment.check_in_time,
        "queue_available": True,
        "queue_size": waiting_patients,
        "emergency_cases": emergency_patients,
        "available_doctors": available_doctors,
        "queue_snapshot_id": queue_snapshot.id,
    }


@router.post("/{appointment_id}/start-consultation")
def start_consultation(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.user_id == current_user.id,
        )
        .first()
    )

    if not appointment:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    if appointment.check_in_time is None:
        raise HTTPException(
            status_code=400,
            detail="Patient must check in first",
        )

    if appointment.consultation_start_time is not None:
        raise HTTPException(
            status_code=400,
            detail="Consultation has already started",
        )

    queue_query = (
        db.query(HospitalQueueStatus)
        .filter(HospitalQueueStatus.hospital_id == appointment.hospital_id)
    )

    if appointment.department:
        queue_query = queue_query.filter(
            HospitalQueueStatus.department == appointment.department
        )

    queue_status = (
        queue_query.order_by(HospitalQueueStatus.updated_at.desc()).first()
    )

    consultation_start = datetime.utcnow()
    appointment.consultation_start_time = consultation_start
    appointment.status = "in_consultation"

    waiting_seconds = (
        consultation_start - appointment.check_in_time
    ).total_seconds()
    waiting_minutes = max(0, round(waiting_seconds / 60))

    observation = HospitalWaitingObservation(
        hospital_id=appointment.hospital_id,
        department=appointment.department,
        appointment_id=appointment.id,
        check_in_time=appointment.check_in_time,
        consultation_start_time=consultation_start,
        waiting_minutes=waiting_minutes,
        queue_size=(queue_status.queue_size if queue_status else None),
        emergency_cases=(queue_status.emergency_cases if queue_status else None),
        available_doctors=(queue_status.available_doctors if queue_status else None),
        observed_at=datetime.utcnow(),
        source="medtour_appointment",
    )

    db.add(observation)
    db.commit()
    db.refresh(appointment)
    db.refresh(observation)

    return {
        "success": True,
        "appointment_id": appointment.id,
        "status": appointment.status,
        "consultation_start_time": appointment.consultation_start_time,
        "actual_waiting_minutes": waiting_minutes,
        "queue_available": queue_status is not None,
        "queue_size": (queue_status.queue_size if queue_status else None),
        "emergency_cases": (queue_status.emergency_cases if queue_status else None),
        "available_doctors": (queue_status.available_doctors if queue_status else None),
        "observation_id": observation.id,
    }
