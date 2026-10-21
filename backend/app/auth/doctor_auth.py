"""
Doctor-side JWT dependency (client/server auth for the /doctor portal).

Separate from app.auth.dependencies.get_current_user: doctors hold their own
token namespace (`role: "doctor"`) issued by /doctor/auth/login so a patient
token can never call the diagnosis endpoints and a doctor token is rejected
by the patient-facing routers.
"""

import os

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.doctor import Doctor

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# tokenUrl is where the client actually posts credentials — the portal calls
# POST /doctor/auth/login with JSON, and Swagger's "Authorize" uses this path.
oauth2_doctor_scheme = OAuth2PasswordBearer(
    tokenUrl="/doctor/auth/login",
    auto_error=False,  # optional: patient scan/claim endpoints live on the same prefix
)


def get_current_doctor(
    token: str = Depends(oauth2_doctor_scheme),
    db: Session = Depends(get_db),
) -> Doctor:
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Doctor sign-in required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate doctor credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "doctor":
            raise credentials_exception
        email = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    doctor = db.query(Doctor).filter(Doctor.email == email).first()
    if doctor is None:
        raise credentials_exception
    return doctor
