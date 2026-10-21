"""
Seed (or reset) the demo/test doctor account.

The portal doctor sees EVERY appointment when `hospital_id` is NULL, so this
account is the single test inbox for all schedules created in the app.

Idempotent: running it twice just resets the password/profile back to the
known demo values instead of failing on the unique constraints.

    cd backend
    .\\venv\\Scripts\\python.exe scripts\\seed_test_doctor.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime

from app.auth.security import hash_password
from app.database.database import SessionLocal
from app.models.doctor import Doctor

# Imported purely so SQLAlchemy can resolve doctors.hospital_id -> hospitals.id.
# Without it the mapper raises NoReferencedTableError on first flush.
from app.models.hospital import Hospital  # noqa: F401

# ---- demo credentials -------------------------------------------------------
TEST_EMAIL = "test@medtour.in"
TEST_PASSWORD = "Test@1234"
TEST_NAME = "Dr. Test Doctor"
TEST_REG_NUMBER = "TEST-2024-0001"
TEST_COUNCIL = "Maharashtra"
TEST_YEAR = "2024"
TEST_SPECIALIZATION = "General Medicine"

# Verification payload cached on the row so /doctor/auth/me answers locally
# and the portal shows a verified badge without calling api.askmydoc.in
# (whose NMC portal fetch is currently returning 503/404).
CACHED_VERIFICATION = {
    "verified": True,
    "cached": True,
    "name": TEST_NAME,
    "reg_number": TEST_REG_NUMBER,
    "state_council": TEST_COUNCIL,
    "year": TEST_YEAR,
    "qualification": "MBBS",
    "status": "verified",
    "reason": None,
    "raw": None,
    "fetched_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
}


def main() -> None:
    db = SessionLocal()
    try:
        doctor = (
            db.query(Doctor)
            .filter(Doctor.email == TEST_EMAIL)
            .first()
        )

        fields = dict(
            full_name=TEST_NAME,
            password=hash_password(TEST_PASSWORD),
            reg_number=TEST_REG_NUMBER,
            state_council=TEST_COUNCIL,
            reg_year=TEST_YEAR,
            specialization=TEST_SPECIALIZATION,
            qualification="MBBS",
            # NULL hospital_id => the doctor is not scoped to one facility and
            # therefore receives ALL appointments (the demo inbox).
            hospital_id=None,
            verified=True,
            verified_at=datetime.utcnow(),
            verification_json=json.dumps(CACHED_VERIFICATION, default=str),
        )

        if doctor:
            for key, value in fields.items():
                setattr(doctor, key, value)
            action = "updated"
        else:
            doctor = Doctor(email=TEST_EMAIL, **fields)
            db.add(doctor)
            action = "created"

        db.commit()
        db.refresh(doctor)

        total = db.query(Doctor).count()
        print(f"[seed] test doctor {action} (id={doctor.id})")
        print(f"[seed] email:    {TEST_EMAIL}")
        print(f"[seed] password: {TEST_PASSWORD}")
        print(f"[seed] verified: {doctor.verified}  hospital_id={doctor.hospital_id}")
        print(f"[seed] doctors in db: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
