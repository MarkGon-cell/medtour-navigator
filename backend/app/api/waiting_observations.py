from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.hospital import Hospital
from app.models.hospital_waiting_observation import (
    HospitalWaitingObservation,
)


router = APIRouter(
    prefix="/waiting-observations",
    tags=["Waiting Time Data"],
)


class WaitingObservationRequest(BaseModel):
    hospital_id: int
    department: str | None = None

    appointment_id: int | None = None

    check_in_time: datetime
    consultation_start_time: datetime

    queue_size: int | None = None
    emergency_cases: int | None = None
    available_doctors: int | None = None


@router.post("")
def create_waiting_observation(
    request: WaitingObservationRequest,
    db: Session = Depends(get_db),
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

    if request.consultation_start_time < request.check_in_time:
        raise HTTPException(
            status_code=400,
            detail="Consultation start time cannot be before check-in time.",
        )

    waiting_seconds = (
        request.consultation_start_time
        - request.check_in_time
    ).total_seconds()

    waiting_minutes = round(waiting_seconds / 60)

    observation = HospitalWaitingObservation(
        hospital_id=request.hospital_id,
        department=request.department,
        appointment_id=request.appointment_id,
        check_in_time=request.check_in_time,
        consultation_start_time=request.consultation_start_time,
        waiting_minutes=waiting_minutes,
        queue_size=request.queue_size,
        emergency_cases=request.emergency_cases,
        available_doctors=request.available_doctors,
        observed_at=datetime.utcnow(),
        source="medtour_system",
    )

    db.add(observation)
    db.commit()
    db.refresh(observation)

    return {
        "success": True,
        "observation_id": observation.id,
        "hospital_id": observation.hospital_id,
        "department": observation.department,
        "waiting_minutes": observation.waiting_minutes,
        "source": observation.source,
    }