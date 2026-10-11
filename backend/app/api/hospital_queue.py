import os

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.hospital import Hospital
from app.models.hospital_queue_status import HospitalQueueStatus


router = APIRouter(
    prefix="/hospitals",
    tags=["Hospital Queue"],
)

# Queue figures feed the waiting-time predictor. Allowing anonymous writes
# would let anyone publish "0 doctors available" for any facility, so this
# is gated the same way as POST /hospitals/. Reads stay public.
HOSPITAL_WRITE_KEY = os.getenv("HOSPITAL_WRITE_KEY")


class QueueStatusRequest(BaseModel):
    department: str | None = None
    queue_size: int
    emergency_cases: int
    available_doctors: int


@router.post("/{hospital_id}/queue")
def update_queue_status(
    hospital_id: int,
    request: QueueStatusRequest,
    x_hospital_write_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not HOSPITAL_WRITE_KEY or x_hospital_write_key != HOSPITAL_WRITE_KEY:
        raise HTTPException(
            status_code=403,
            detail="Queue updates require a valid hospital write key.",
        )

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

    if request.queue_size < 0:
        raise HTTPException(
            status_code=400,
            detail="Queue size cannot be negative",
        )

    if request.emergency_cases < 0:
        raise HTTPException(
            status_code=400,
            detail="Emergency cases cannot be negative",
        )

    if request.available_doctors < 0:
        raise HTTPException(
            status_code=400,
            detail="Available doctors cannot be negative",
        )

    queue_status = HospitalQueueStatus(
        hospital_id=hospital_id,
        department=request.department,
        queue_size=request.queue_size,
        emergency_cases=request.emergency_cases,
        available_doctors=request.available_doctors,
        updated_at=datetime.utcnow(),
    )

    db.add(queue_status)
    db.commit()
    db.refresh(queue_status)

    return {
        "success": True,
        "hospital_id": hospital_id,
        "department": queue_status.department,
        "queue_size": queue_status.queue_size,
        "emergency_cases": queue_status.emergency_cases,
        "available_doctors": queue_status.available_doctors,
        "updated_at": queue_status.updated_at,
    }

@router.get("/{hospital_id}/queue")
def get_queue_status(
    hospital_id: int,
    department: str | None = None,
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

    query = (
        db.query(HospitalQueueStatus)
        .filter(
            HospitalQueueStatus.hospital_id == hospital_id
        )
    )

    if department:
        query = query.filter(
            HospitalQueueStatus.department == department
        )

    queue_status = (
        query
        .order_by(HospitalQueueStatus.updated_at.desc())
        .first()
    )

    if not queue_status:
        return {
            "queue_available": False,
            "message": "Current queue information is not available.",
        }

    return {
        "queue_available": True,
        "hospital_id": hospital_id,
        "department": queue_status.department,
        "queue_size": queue_status.queue_size,
        "emergency_cases": queue_status.emergency_cases,
        "available_doctors": queue_status.available_doctors,
        "updated_at": queue_status.updated_at,
    }