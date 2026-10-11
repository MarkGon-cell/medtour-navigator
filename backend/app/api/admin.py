"""
DEPRECATED -- this router is no longer mounted by app/main.py.

Per docs/architecture.md section 7 the admin console is retired: it existed
to review SOS alerts (which are no longer written) and moderate appointments
(which are now guest-local). Its endpoints were also reachable without any
server-side auth -- `_verify_admin()` exists below but was never wired in as
a FastAPI dependency, so every /admin/* route was effectively public behind
a client-side check with a hardcoded password.

Kept on disk only as a reference implementation. Delete once the frontend
/admin route is removed (project_progress.md, Phase 4).
"""

import os
import json
import glob
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.hospital import Hospital
from app.models.user import User
from app.models.sos_alert import SOSAlert

router = APIRouter(
    prefix="/admin",
    tags=["Admin Moderation"],
)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SOS_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sos_logs")


class AdminAuthRequest(BaseModel):
    password: str


class AdminStatusUpdateRequest(BaseModel):
    status: str


def _verify_admin(x_admin_password: Optional[str] = Header(None)):
    # Accept header authentication or standard fallback for basic scaffolding
    if x_admin_password and (x_admin_password == ADMIN_PASSWORD or x_admin_password == "admin"):
        return True
    return False


@router.post("/verify")
def verify_admin_login(req: AdminAuthRequest):
    pwd = req.password.strip()
    if pwd == ADMIN_PASSWORD or pwd == "admin" or pwd == "admin123":
        return {
            "success": True,
            "message": "Admin credentials verified",
            "authenticated": True,
        }
    raise HTTPException(status_code=401, detail="Invalid admin password")


# -------------------------------------------------------------------
# SOS Moderation Endpoints
# -------------------------------------------------------------------

def _sync_sos_logs_to_db(db: Session):
    """Sync file-based JSON logs into the database if not already present."""
    if not os.path.exists(SOS_LOG_DIR):
        return

    json_files = glob.glob(os.path.join(SOS_LOG_DIR, "sos_*.json"))
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Check if exists by timestamp or log_path
            existing = db.query(SOSAlert).filter(
                (SOSAlert.log_path == file_path) |
                (SOSAlert.address == data.get("address")) &
                (SOSAlert.latitude == data.get("latitude"))
            ).first()

            if not existing:
                ts_str = data.get("timestamp")
                dt = datetime.utcnow()
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass

                sos = SOSAlert(
                    user_id=data.get("user_id"),
                    user_name=data.get("user_name"),
                    email=data.get("email"),
                    latitude=float(data.get("latitude", 0.0)),
                    longitude=float(data.get("longitude", 0.0)),
                    address=data.get("address", "Unknown"),
                    pincode=data.get("pincode"),
                    message=data.get("message"),
                    contact_emergency_services=data.get("contact_emergency_services", True),
                    status="PENDING",
                    log_path=file_path,
                    created_at=dt,
                )
                db.add(sos)
        except Exception as e:
            continue
    try:
        db.commit()
    except Exception:
        db.rollback()


@router.get("/sos-alerts")
def get_sos_alerts(
    status: Optional[str] = Query(None, description="Filter by status: PENDING, DISPATCHED, RESOLVED, CANCELLED"),
    db: Session = Depends(get_db),
):
    _sync_sos_logs_to_db(db)

    query = db.query(SOSAlert)
    if status:
        query = query.filter(SOSAlert.status == status.strip().upper())

    alerts = query.order_by(SOSAlert.created_at.desc()).all()

    result = []
    for a in alerts:
        result.append({
            "id": a.id,
            "user_id": a.user_id,
            "user_name": a.user_name or (a.user.full_name if a.user else "Anonymous / Guest"),
            "email": a.email or (a.user.email if a.user else None),
            "latitude": a.latitude,
            "longitude": a.longitude,
            "address": a.address,
            "pincode": a.pincode,
            "message": a.message,
            "contact_emergency_services": a.contact_emergency_services,
            "status": a.status,
            "google_maps_url": f"https://www.google.com/maps?q={a.latitude},{a.longitude}",
            "created_at": a.created_at,
            "updated_at": a.updated_at,
        })
    return result


@router.patch("/sos-alerts/{alert_id}/status")
def update_sos_status(
    alert_id: int,
    req: AdminStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="SOS Alert not found")

    new_status = req.status.strip().upper()
    valid_statuses = ["PENDING", "DISPATCHED", "RESOLVED", "CANCELLED"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SOS status '{req.status}'. Must be one of: {valid_statuses}",
        )

    alert.status = new_status
    alert.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(alert)

    return {
        "success": True,
        "id": alert.id,
        "status": alert.status,
        "updated_at": alert.updated_at,
    }


@router.delete("/sos-alerts/{alert_id}")
def delete_sos_alert(
    alert_id: int,
    db: Session = Depends(get_db),
):
    alert = db.query(SOSAlert).filter(SOSAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="SOS Alert not found")

    db.delete(alert)
    db.commit()
    return {"success": True, "message": "SOS Alert deleted successfully"}


# -------------------------------------------------------------------
# Appointment Moderation Endpoints
# -------------------------------------------------------------------

@router.get("/appointments")
def get_all_appointments(
    status: Optional[str] = Query(None, description="Filter: upcoming, completed, cancelled, all"),
    db: Session = Depends(get_db),
):
    query = db.query(Appointment)

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

    result = []
    for app in appointments:
        result.append({
            "id": app.id,
            "user_id": app.user_id,
            "user_name": app.user.full_name if app.user else "Patient",
            "user_email": app.user.email if app.user else "N/A",
            "hospital_id": app.hospital_id,
            "hospital_name": app.hospital.name if app.hospital else "Hospital",
            "hospital_city": app.hospital.city if app.hospital else None,
            "hospital_state": app.hospital.state if app.hospital else None,
            "department": app.department,
            "appointment_time": app.appointment_time,
            "status": app.status,
            "symptoms": app.symptoms,
            "is_emergency": app.is_emergency,
            "check_in_time": app.check_in_time,
            "consultation_start_time": app.consultation_start_time,
            "created_at": app.created_at,
            "updated_at": app.updated_at,
        })
    return result


@router.patch("/appointments/{appointment_id}/status")
def update_appointment_status(
    appointment_id: int,
    req: AdminStatusUpdateRequest,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    new_status = req.status.strip().lower()
    valid_statuses = ["upcoming", "completed", "cancelled", "checked_in", "in_consultation", "booked"]
    if new_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{req.status}'. Must be one of: {valid_statuses}",
        )

    appointment.status = new_status
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    return {
        "success": True,
        "id": appointment.id,
        "status": appointment.status,
        "updated_at": appointment.updated_at,
    }


@router.delete("/appointments/{appointment_id}")
def delete_admin_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment).filter(Appointment.id == appointment_id).first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    db.delete(appointment)
    db.commit()
    return {"success": True, "message": "Appointment removed successfully"}
