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
from app.models.hospital import Hospital
from app.models.curated_hospital import CuratedHospital
from app.models.hospital_availability import HospitalAvailability
from app.models.hospital_waiting_prediction import HospitalWaitingPrediction
from app.models.hospital_waiting_observation import HospitalWaitingObservation
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital_queue_status import HospitalQueueStatus
from app.models.sos_alert import SOSAlert
from app.models.google_search_usage import GoogleSearchUsage

from app.api.hospitals import router as hospital_router
from app.api.waiting_prediction import router as waiting_prediction_router
from app.api.waiting_observations import router as waiting_observations_router
from app.api.appointments import router as appointments_router
from app.api.hospital_queue import router as hospital_queue_router
from app.api.emergency import router as emergency_router
from app.api.ai_analysis import router as ai_router
from app.api.google_ai_search import router as google_ai_search_router
from app.api.mtr_vault import router as mtr_vault_router
from app.api.doctor import router as doctor_router
from app.api.doctor_auth import router as doctor_auth_router
from app.api.verification import router as verification_router

# app.api.admin was deleted along with the `users` table it administered. The
# admin console was already deprecated by the redesign and unauthenticated
# with a hardcoded password; nothing mounted it.

Base.metadata.create_all(bind=engine)


def _is_sqlite() -> bool:
    return engine.dialect.name == "sqlite"


def _ensure_discovery_columns() -> None:
    """
    Add the columns `GET /hospitals/discover` writes, if they are missing.

    `create_all` only creates missing *tables*; it never adds a column to an
    existing one. Worse, `scripts/import_hospitals.py` rebuilds `hospitals`
    from a pandas DataFrame that carries none of these fields, silently
    dropping them. Re-adding on every startup makes both paths converge.

    Runs after `create_all` so a fresh database already has the table.
    On SQLite the Postgres-specific sequence / IF-NOT-EXISTS statements are
    skipped (SQLite cannot ALTER ADD COLUMN IF NOT EXISTS); create_all on a
    fresh SQLite file already has the full schema from the ORM models.
    """
    if _is_sqlite():
        return

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


def _ensure_appointment_columns() -> None:
    """
    Converge `appointments` on the status-only schema.

    The appointment row used to carry clinical detail (diagnosis,
    prescription, notes), visit lifecycle timestamps and a patient account
    FK. All of that is gone: clinical and lifecycle data now live on the
    patient's device and in their `.mtr`, and there are no patient accounts.

    `create_all` only creates missing *tables* — it never drops a column or
    alters an existing one — so an existing database is brought forward here,
    one statement at a time, tolerating whichever are already applied.
    """
    if _is_sqlite():
        return

    add = (
        # The derived unique id everything keys on.
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS appointment_code VARCHAR",
        # Row labels the portal shows: who and why. Not an account.
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS patient_name VARCHAR",
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS reason TEXT",
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS hospital_name VARCHAR",
        # The two flags the flow actually cares about.
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_completed BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT FALSE",
        # Stage-2 flag: a discharge QR has actually been minted.
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS qr_minted BOOLEAN NOT NULL DEFAULT FALSE",
        # Who treated the visit (stamped at diagnosis time).
        "ALTER TABLE appointments ADD COLUMN IF NOT EXISTS doctor_name VARCHAR",
    )

    # Columns that must go. Clinical text is the important one: it must not
    # sit in a table the moment the product promises it never will.
    drop = (
        "user_id",
        "symptoms",
        "is_emergency",
        "check_in_time",
        "consultation_start_time",
        "consultation_end_time",
        "diagnosis",
        "prescription",
        "diagnosis_notes",
        "qr_verified",
        "completed_at",
        "claim_purchased",
        "claim_purchased_at",
        "assigned_doctor",
    )

    with engine.begin() as connection:
        for statement in add:
            connection.execute(text(statement))

        # Backfill the new columns from the old ones before dropping them, so
        # rows booked under the previous schema keep their meaning.
        #
        # Each statement names an *old* column as its source, so each is only
        # safe while that column still exists. A run that previously got as
        # far as the DROP phase (or a database already converted by hand)
        # leaves the source gone — running the UPDATE then would abort the
        # whole migration mid-way and leave `appointment_code` nullable, which
        # in turn breaks every downstream endpoint. Hence: check first.
        existing = {
            row[0]
            for row in connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'appointments'"
                )
            )
        }

        backfills = (
            # (source column that must still exist, statement)
            ("symptoms", "UPDATE appointments SET reason = symptoms WHERE reason IS NULL"),
            (
                "assigned_doctor",
                "UPDATE appointments SET doctor_name = assigned_doctor "
                "WHERE doctor_name IS NULL",
            ),
            (
                "status",
                "UPDATE appointments SET is_completed = TRUE WHERE status = 'completed'",
            ),
            (
                "claim_purchased",
                "UPDATE appointments SET is_verified = TRUE WHERE claim_purchased IS TRUE",
            ),
            # Rows created before the derived-id scheme keep whatever code
            # they already had; only the empty ones get minted. No old column
            # involved, so it always runs.
            (
                None,
                "UPDATE appointments SET appointment_code = "
                "'MT-' || upper(substr(md5(random()::text || id::text), 1, 8)) "
                "WHERE appointment_code IS NULL",
            ),
        )
        for source, statement in backfills:
            if source is not None and source not in existing:
                continue
            connection.execute(text(statement))

        # Derived from a plain FK, so it is safe to backfill on its own: the
        # directory always has the name, whatever shape `appointments` was in.
        connection.execute(
            text(
                "UPDATE appointments SET hospital_name = "
                "(SELECT name FROM hospitals WHERE hospitals.id = appointments.hospital_id) "
                "WHERE hospital_name IS NULL"
            )
        )

        for column in drop:
            # IF EXISTS keeps this re-runnable; each column may or may not be
            # there depending on which schema generation the database is on.
            connection.execute(
                text(f"ALTER TABLE appointments DROP COLUMN IF EXISTS {column}")
            )

        # `appointment_code` is the identity of the whole flow — no row
        # without one can be scanned, diagnosed or claimed.
        connection.execute(
            text("ALTER TABLE appointments ALTER COLUMN appointment_code SET NOT NULL")
        )
        connection.execute(
            text("ALTER TABLE appointments ALTER COLUMN patient_name SET NOT NULL")
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_appointments_appointment_code "
                "ON appointments (appointment_code)"
            )
        )

        # There are no patient accounts. The `users` table and everything that
        # pointed at it go with them.
        connection.execute(text("DROP TABLE IF EXISTS users CASCADE"))

        # SOS logs carry no identity either — only where the call came from
        # and where it sits in the dispatch lifecycle.
        for column in ("user_id", "user_name", "email"):
            connection.execute(
                text(f"ALTER TABLE sos_alerts DROP COLUMN IF EXISTS {column}")
            )


_ensure_appointment_columns()

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
# Patient sign-in is gone entirely: there are no patient accounts, so
# /auth/register, /auth/login and /profile no longer exist. Doctors hold their
# own separate token namespace under /doctor/auth. See docs/FRONTEND.md §1.
app.include_router(hospital_router)
app.include_router(waiting_prediction_router)
app.include_router(waiting_observations_router)
app.include_router(appointments_router)
app.include_router(hospital_queue_router)
app.include_router(emergency_router)
app.include_router(ai_router)
app.include_router(google_ai_search_router)
app.include_router(mtr_vault_router)
app.include_router(doctor_router)
app.include_router(doctor_auth_router)
# Public: the destination of the QR printed on the mediclaim PDF.
app.include_router(verification_router)


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
                "/ai/google-search  (Google AI Mode; 2 uses/day/device)",
                "/waiting-time/predict",
            ],
            "active_readded": [
                "/emergency/sos  (dispatch packet to nearest ER: caller also dials 112)",
            ],
            "doctor_portal": [
                "/doctor/auth/register, /doctor/auth/login, /doctor/auth/me, /doctor/auth/reverify",
                "/doctor/appointments  (GET: portal list)",
                "/doctor/diagnosis  (POST: mint the discharge QR — clinical text is NOT stored)",
                "/doctor/qr  (POST: re-mint the QR from the doctor's local copy)",
                "/doctor/appointment/{code}  (GET)",
                "/doctor/scan  (POST: public — match the code, set is_completed)",
                "/doctor/claim/purchase  (POST: public — pay once, backend renders the PDF)",
                "/doctor/claim/pdf  (POST: public — free re-download after purchase)",
                "/doctor/claim/{code}  (GET: public — claim status, no PDF)",
            ],
            "verification": [
                "/verificationStatus?aid=MT-XXXXXXXX  (public — what the PDF's QR resolves to)",
            ],
            "removed": [
                "/auth, /profile  (no patient accounts exist — doctors only)",
                "/appointments/* except POST  (visits are guest-local)",
                "/admin  (deleted with the users table)",
            ],
        },
    }


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "MedTour Navigator"}


@app.get("/v1/models")
def list_v1_models():
    """Compatibility endpoint for AI tools and OpenAI-compatible clients querying available models."""
    return {
        "object": "list",
        "data": [
            {
                "id": "medtour-ai",
                "object": "model",
                "created": 1700000000,
                "owned_by": "medtour-navigator",
            },
            {
                "id": "gpt-4o",
                "object": "model",
                "created": 1700000000,
                "owned_by": "openai",
            },
            {
                "id": "llama-3.1-70b-instruct",
                "object": "model",
                "created": 1700000000,
                "owned_by": "meta",
            },
        ],
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
