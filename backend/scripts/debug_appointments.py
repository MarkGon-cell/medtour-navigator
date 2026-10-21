"""Debug helper: dump appointments + doctor scope from Postgres."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.database.database import SessionLocal

db = SessionLocal()
try:
    rows = db.execute(
        text(
            "SELECT id, appointment_code, patient_name, reason, hospital_id, "
            "hospital_name, doctor_name, status, is_completed, is_verified "
            "FROM appointments ORDER BY id"
        )
    ).fetchall()
    print("total appointments:", len(rows))
    for r in rows[:40]:
        print(
            "  id=%s code=%s name=%r hosp=%s(%s) doc=%r status=%s completed=%s verified=%s"
            % (r[0], r[1], r[2], r[4], r[5], r[6], r[7], r[8], r[9])
        )

    docs = db.execute(
        text("SELECT id, email, full_name, hospital_id, verified FROM doctors")
    ).fetchall()
    print("doctors:", docs)

    cols = db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='appointments' ORDER BY ordinal_position"
        )
    ).fetchall()
    print("appointment columns:", [c[0] for c in cols])
finally:
    db.close()
