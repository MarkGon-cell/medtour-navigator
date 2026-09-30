from datetime import datetime

from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException
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
)
from app.auth.dependencies import get_current_user
from app.models.hospital_queue_status import HospitalQueueStatus


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)

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
        status="booked",
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment

@router.get("", response_model=list[AppointmentResponse])
def get_my_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointments = (
        db.query(Appointment)
        .filter(Appointment.user_id == current_user.id)
        .order_by(Appointment.appointment_time.desc())
        .all()
    )

    return appointments

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

    # ---------------------------------------------
    # Mark patient as checked in
    # ---------------------------------------------

    appointment.check_in_time = datetime.utcnow()
    appointment.status = "checked_in"

    db.commit()
    db.refresh(appointment)

    # ---------------------------------------------
    # Automatically calculate current queue
    # ---------------------------------------------

    queue_query = (
        db.query(Appointment)
        .filter(
            Appointment.hospital_id
            == appointment.hospital_id,

            Appointment.status
            == "checked_in",
        )
    )

    if appointment.department:
        queue_query = queue_query.filter(
            Appointment.department
            == appointment.department
        )

    waiting_patients = queue_query.count()

    emergency_patients = (
        queue_query
        .filter(
            Appointment.is_emergency == True
        )
        .count()
    )

    # ---------------------------------------------
    # Get latest available doctor count
    # ---------------------------------------------

    latest_queue = (
        db.query(HospitalQueueStatus)
        .filter(
            HospitalQueueStatus.hospital_id
            == appointment.hospital_id
        )
    )

    if appointment.department:
        latest_queue = latest_queue.filter(
            HospitalQueueStatus.department
            == appointment.department
        )

    latest_queue = (
        latest_queue
        .order_by(
            HospitalQueueStatus.updated_at.desc()
        )
        .first()
    )

    available_doctors = (
        latest_queue.available_doctors
        if latest_queue
        else None
    )

    # ---------------------------------------------
    # Store queue snapshot
    # ---------------------------------------------

    queue_snapshot = HospitalQueueStatus(
    hospital_id=appointment.hospital_id,
    department=appointment.department,
    queue_size=waiting_patients,
    emergency_cases=emergency_patients,
    available_doctors=(
        available_doctors
        if available_doctors is not None
        else 0
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

    # --------------------------------------------------
    # Get latest queue information for this hospital
    # --------------------------------------------------

    queue_query = (
        db.query(HospitalQueueStatus)
        .filter(
            HospitalQueueStatus.hospital_id
            == appointment.hospital_id
        )
    )

    if appointment.department:
        queue_query = queue_query.filter(
            HospitalQueueStatus.department
            == appointment.department
        )

    queue_status = (
        queue_query
        .order_by(
            HospitalQueueStatus.updated_at.desc()
        )
        .first()
    )

    # --------------------------------------------------
    # Record consultation start
    # --------------------------------------------------

    consultation_start = datetime.utcnow()

    appointment.consultation_start_time = consultation_start
    appointment.status = "in_consultation"

    # Calculate actual waiting time
    waiting_seconds = (
        consultation_start - appointment.check_in_time
    ).total_seconds()

    waiting_minutes = max(
        0,
        round(waiting_seconds / 60)
    )

    # --------------------------------------------------
    # Create waiting-time observation
    # --------------------------------------------------

    observation = HospitalWaitingObservation(
        hospital_id=appointment.hospital_id,
        department=appointment.department,
        appointment_id=appointment.id,

        check_in_time=appointment.check_in_time,
        consultation_start_time=consultation_start,

        waiting_minutes=waiting_minutes,

        queue_size=(
            queue_status.queue_size
            if queue_status
            else None
        ),

        emergency_cases=(
            queue_status.emergency_cases
            if queue_status
            else None
        ),

        available_doctors=(
            queue_status.available_doctors
            if queue_status
            else None
        ),

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

        "consultation_start_time":
            appointment.consultation_start_time,

        "actual_waiting_minutes":
            waiting_minutes,

        "queue_available":
            queue_status is not None,

        "queue_size": (
            queue_status.queue_size
            if queue_status
            else None
        ),

        "emergency_cases": (
            queue_status.emergency_cases
            if queue_status
            else None
        ),

        "available_doctors": (
            queue_status.available_doctors
            if queue_status
            else None
        ),

        "observation_id":
            observation.id,
    }