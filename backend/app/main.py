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
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends

from app.database.database import Base, engine, get_db
from app.models.user import User
from app.models.hospital import Hospital
from app.models.curated_hospital import CuratedHospital
from app.models.hospital_availability import HospitalAvailability
from app.models.hospital_waiting_prediction import HospitalWaitingPrediction
from app.models.hospital_waiting_observation import HospitalWaitingObservation
from app.models.appointment import Appointment
from app.models.hospital_queue_status import HospitalQueueStatus
from app.models.sos_alert import SOSAlert
from app.models.google_search_usage import GoogleSearchUsage

from app.auth.auth import router as auth_router
from app.auth.dependencies import get_current_user
from app.api.hospitals import router as hospital_router
from app.api.waiting_prediction import router as waiting_prediction_router
from app.api.waiting_observations import router as waiting_observations_router
from app.api.appointments import router as appointments_router
from app.api.hospital_queue import router as hospital_queue_router
from app.api.emergency import router as emergency_router
from app.api.ai_analysis import router as ai_router
from app.api.google_ai_search import router as google_ai_search_router
from app.api.mtr_vault import router as mtr_vault_router

# app.api.admin is intentionally NOT mounted: the admin console is deprecated
# by the redesign (docs/architecture.md section 7). Its endpoints were also
# unauthenticated with a hardcoded password. See that module for details.

Base.metadata.create_all(bind=engine)


def _ensure_discovery_columns() -> None:
    """
    Add the columns `GET /hospitals/discover` writes, if they are missing.

    `create_all` only creates missing *tables*; it never adds a column to an
    existing one. Worse, `scripts/import_hospitals.py` rebuilds `hospitals`
    from a pandas DataFrame that carries none of these fields, silently
    dropping them. Re-adding on every startup makes both paths converge.

    Runs after `create_all` so a fresh database already has the table.
    """
    statements = (
        # -- Primary key ------------------------------------------------
        # pandas `to_sql(if_exists="replace")` created `id` as a bare
        # `bigint NOT NULL` with no default and no identity column, so
        # SQLAlchemy omits it from the INSERT and Postgres has nothing to
        # fill it with: every insert into `hospitals` raised
        # NotNullViolation. That included the pre-existing POST /hospitals/,
        # which would have failed the first time anyone used it.
        "CREATE SEQUENCE IF NOT EXISTS hospitals_id_seq",
        "ALTER TABLE hospitals "
        "ALTER COLUMN id SET DEFAULT nextval('hospitals_id_seq')",
        "ALTER SEQUENCE hospitals_id_seq OWNED BY hospitals.id",
        # Never let the sequence hand out an id the directory already uses.
        "SELECT setval('hospitals_id_seq', "
        "GREATEST(COALESCE((SELECT MAX(id) FROM hospitals), 0), 0) + 1, false)",
        # -- Discovery provenance ---------------------------------------
        "ALTER TABLE hospitals "
        "ADD COLUMN IF NOT EXISTS source VARCHAR NOT NULL DEFAULT 'csv_import'",
        "ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS external_id VARCHAR",
        "ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS opening_hours VARCHAR",
        # Reputation: nullable, stays NULL until a real ratings source loads.
        "ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS rating DOUBLE PRECISION",
        "ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS review_count INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_hospitals_external_id "
        "ON hospitals (external_id)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


_ensure_discovery_columns()

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

# Authenticated routers below are DEPRECATED but still mounted: sign-in is
# optional and nothing in the redesigned frontend links to /login or /register
# (docs/FRONTEND.md section 1). Kept so previously signed-in users do not lose
# their records mid-flight. See docs/project_progress.md Phase 4.
app.include_router(auth_router)
app.include_router(hospital_router)
app.include_router(waiting_prediction_router)
app.include_router(waiting_observations_router)
app.include_router(appointments_router)
app.include_router(hospital_queue_router)
app.include_router(emergency_router)
app.include_router(ai_router)
app.include_router(google_ai_search_router)
app.include_router(mtr_vault_router)


@app.get("/")
def root():
    return {
        "message": "MedTour Navigator API Running",
        "version": "2.0",
        "endpoints": {
            "active": [
                "/hospitals/nearby  (bounding-box; sort=distance|emergency; limit)",
                "/hospitals/keywords  (POST: 5 AI name-keywords for a symptom line)",
                "/hospitals/by-keywords  (keyword index; distance low -> high)",
                "/hospitals/by-pincode  (pincode from lat/long; distance low -> high)",
                "/hospitals/{id}",
                "/hospitals/search",
                "/hospitals/{id}/availability",
                "/hospitals/{id}/queue  (GET public; POST needs X-Hospital-Write-Key)",
                "/ai/analyze",
                "/ai/google-search  (Google AI Mode; 2 uses/day/user)",
                "/waiting-time/predict",
            ],
            "deprecated": [
                "/auth  (guest-first: nothing requires sign-in)",
                "/appointments  (visits are guest-local)",
                "/profile",
            ],
            "active_readded": [
                "/emergency/sos  (dispatch packet to nearest ER: caller also dials 112)",
            ],
            "not_mounted": [
                "/admin  (removed: unauthenticated moderation console)",
            ],
        },
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MedTour Navigator"}


@app.get("/profile")
def profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deprecated: guest-first sessions do not have a profile to fetch."""
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
