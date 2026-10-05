import os
import json
import sys
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.auth.dependencies import get_optional_current_user
from app.models.user import User

router = APIRouter(prefix="/emergency", tags=["Emergency"])


class SOSRequest(BaseModel):
    latitude: float
    longitude: float
    address: str
    pincode: Optional[str] = None
    message: Optional[str] = None
    contact_emergency_services: bool = True


SOS_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "sos_logs")
os.makedirs(SOS_LOG_DIR, exist_ok=True)


def _write_sos_json(record: dict) -> str:
    timestamp = record["timestamp"]
    clean_ts = timestamp.replace(":", "-").replace(" ", "_")
    filename = f"sos_{clean_ts}.json"
    path = os.path.join(SOS_LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path


@router.post("/sos")
def trigger_sos(
    req: SOSRequest,
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    now = datetime.utcnow().isoformat() + "Z"
    user_email = current_user.email if current_user else "Anonymous / Guest"
    user_name = current_user.full_name if current_user and hasattr(current_user, "full_name") else "Anonymous"

    record = {
        "timestamp": now,
        "user_id": current_user.id if current_user else None,
        "user_name": user_name,
        "email": user_email,
        "latitude": req.latitude,
        "longitude": req.longitude,
        "address": req.address,
        "pincode": req.pincode,
        "message": req.message or "Immediate emergency assistance required",
        "contact_emergency_services": req.contact_emergency_services,
    }

    log_path = _write_sos_json(record)
    gmaps_url = f"https://www.google.com/maps?q={req.latitude},{req.longitude}"

    # Stream structured output to backend terminal logs without emoji encoding errors
    log_banner = f"""
======================================================================
[EMERGENCY SOS ALERT RECEIVED]
----------------------------------------------------------------------
Timestamp       : {now}
User            : {user_name} ({user_email})
Location Name   : {req.address}
Pincode         : {req.pincode or 'Not specified'}
Coordinates     : Latitude: {req.latitude}, Longitude: {req.longitude}
Google Maps Link: {gmaps_url}
SOS Message     : {req.message or 'Immediate medical assistance needed'}
Ambulance Req.  : {'[YES] DISPATCH REQUESTED' if req.contact_emergency_services else '[NO]'}
Saved Log File  : {log_path}
======================================================================
"""
    try:
        print(log_banner, flush=True)
    except Exception:
        pass

    ambulance_dispatch = {
        "simulated": True,
        "status": "DISPATCH_INITIATED" if req.contact_emergency_services else "NOT_REQUESTED",
        "eta_minutes": 8 if req.contact_emergency_services else None,
        "nearest_ambulance_service": "108 Emergency Medical Services",
        "gmaps_url": gmaps_url,
        "log_path": log_path,
    }

    return {
        "status": "success",
        "message": "SOS alert received and emergency dispatch logged",
        "timestamp": now,
        "location": {
            "latitude": req.latitude,
            "longitude": req.longitude,
            "address": req.address,
            "pincode": req.pincode,
            "google_maps": gmaps_url
        },
        "ambulance": ambulance_dispatch,
        "log_path": log_path,
    }
