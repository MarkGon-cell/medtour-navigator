import sys
import os

# Ensure safe UTF-8 output across Windows consoles without charmap crashes
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database.database import Base, engine, get_db
from app.models.user import User
from app.models.hospital import Hospital
from app.models.hospital_availability import HospitalAvailability
from app.models.hospital_waiting_prediction import HospitalWaitingPrediction
from app.models.hospital_waiting_observation import HospitalWaitingObservation
from app.models.appointment import Appointment
from app.models.hospital_queue_status import HospitalQueueStatus

from app.auth.auth import router as auth_router
from app.auth.dependencies import get_current_user
from app.api.hospitals import router as hospital_router
from app.api.waiting_prediction import router as waiting_prediction_router
from app.api.waiting_observations import router as waiting_observations_router
from app.api.appointments import router as appointments_router
from app.api.hospital_queue import router as hospital_queue_router
from app.api.emergency import router as emergency_router
from app.api.ai_analysis import router as ai_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MedTour Navigator API",
    version="2.0"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers
app.include_router(auth_router)
app.include_router(hospital_router)
app.include_router(waiting_prediction_router)
app.include_router(waiting_observations_router)
app.include_router(appointments_router)
app.include_router(hospital_queue_router)
app.include_router(emergency_router)
app.include_router(ai_router)


@app.get("/")
def root():
    return {
        "message": "MedTour Navigator API Running",
        "version": "2.0",
        "endpoints": [
            "/auth",
            "/hospitals",
            "/emergency/sos",
            "/ai/analyze",
            "/appointments",
            "/hospital-queue",
            "/waiting-predictions"
        ]
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MedTour Navigator"}


@app.get("/profile")
def profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.email == current_user.email
    ).first()

    if not user:
        return {
            "message": "User not found"
        }

    return {
        "message": "Welcome!",
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = str(exc)
    try:
        print(f"[ERROR] Unhandled exception on {request.url.path}: {error_msg}", flush=True)
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": error_msg}
    )
