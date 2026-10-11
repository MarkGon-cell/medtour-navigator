"""
DEPRECATED -- simulated ambulance dispatch. No longer imported by anything.

This module faked a dispatch pipeline: it slept 100ms, then returned
`{"status": "dispatched", "eta_minutes": 8, "unit": "108 Emergency Medical
Services"}` for a request that contacted nobody. app/api/emergency.py used to
call it, which is where the UI's "help is on the way" promise came from.

Per docs/architecture.md section 8, MedTour must not build an unmonitored
dispatch backend. Real dispatch is `tel:112` from the user's handset.

Kept on disk only as a record of what was removed; safe to delete.
"""

import asyncio
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
import json
import os
import requests
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()

class SOSRequest(BaseModel):
    latitude: float
    longitude: float
    address: str
    pincode: Optional[str] = None
    message: Optional[str] = None
    contact_emergency_services: bool = True

SOS_LOG_DIR = "/tmp/sos_logs"
os.makedirs(SOS_LOG_DIR, exist_ok=True)

def _write_sos_json(record: dict) -> str:
    """Write SOS record to JSON file for logging."""
    timestamp = record["timestamp"]
    clean_ts = timestamp.replace(":", "-").replace(" ", "_")
    filename = f"sos_{clean_ts}.json"
    path = os.path.join(SOS_LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    return path

async def _notify_ambulance_services(payload: dict):
    """Notify ambulance dispatch services (simulated)."""
    try:
        # Simulate API call to ambulance dispatch
        await asyncio.sleep(0.1)  # Simulate network latency
        
        # In production, this would make an actual HTTP request to
        # ambulance dispatch services with the payload
        notification = {
            "alert_id": payload.get("alert_id"),
            "timestamp": payload.get("timestamp"),
            "location": payload.get("location"),
            "patient": payload.get("user_name", "Anonymous"),
            "urgency": "high",
            "status": "dispatched"
        }
        
        logger.info("Ambulance services notified", notification=notification)
        return {"status": "dispatched", "eta_minutes": 8, "unit": "108 Emergency Medical Services"}
        
    except Exception as e:
        logger.error("Failed to notify ambulance services", error=str(e))
        raise

def _format_sos_response(payload: dict, dispatch_result: dict) -> dict:
    """Format the final SOS response."""
    return {
        "status": "success",
        "message": "SOS alert received and emergency dispatch logged",
        "timestamp": payload.get("timestamp"),
        "location": {
            "latitude": payload.get("latitude"),
            "longitude": payload.get("longitude"),
            "address": payload.get("address"),
            "pincode": payload.get("pincode"),
            "google_maps": f"https://www.google.com/maps?q={payload.get('latitude')},{payload.get('longitude')}"
        },
        "ambulance": dispatch_result,
        "log_path": payload.get("log_path"),
        "alert_id": payload.get("alert_id")
    }

async def process_sos_request(request: SOSRequest, background_tasks: BackgroundTasks) -> dict:
    """Process SOS request with proper error handling and logging."""
    now = datetime.utcnow()
    now_iso = now.isoformat() + "Z"
    
    # Generate unique alert ID
    alert_id = f"sos_{int(now.timestamp())}_{hash(request.address)}"
    
    # Log file path for tracking
    record = {
        "alert_id": alert_id,
        "timestamp": now_iso,
        "latitude": request.latitude,
        "longitude": request.longitude,
        "address": request.address,
        "pincode": request.pincode,
        "message": request.message or "Immediate emergency assistance required",
        "contact_emergency_services": request.contact_emergency_services,
        "user_id": None,  # Optional anonymous support
        "user_name": "Anonymous / Guest",
        "email": "Not provided",
    }
    
    log_path = _write_sos_json(record)
    
    # Dispatch ambulance in background
    async def dispatch_async():
        try:
            return await _notify_ambulance_services(record)
        except Exception as e:
            logger.error("Background ambulance dispatch failed", error=str(e))
            return {"status": "failed", "error": "Dispatch service unavailable"}
    
    # Schedule background dispatch
    dispatch_task = asyncio.create_task(dispatch_async())
    background_tasks.add_task(dispatch_task)
    
    # Get dispatch result
    try:
        dispatch_result = await dispatch_task
    except Exception as e:
        logger.error("Dispatch failed", error=str(e))
        dispatch_result = {"status": "failed", "error": str(e)}
    
    return _format_sos_response(record, dispatch_result)