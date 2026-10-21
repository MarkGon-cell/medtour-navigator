"""Schemas for the doctor client/server auth flow (register/login/profile)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class DoctorRegisterInput(BaseModel):
    full_name: str = Field(..., min_length=3, max_length=120)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    reg_number: str = Field(..., min_length=3, max_length=40)
    state_council: Optional[str] = Field(None, max_length=80)
    year: Optional[str] = Field(None, max_length=8)
    specialization: Optional[str] = Field(None, max_length=120)
    qualification: Optional[str] = Field(None, max_length=120)
    phone: Optional[str] = Field(None, max_length=20)
    hospital_id: Optional[int] = None


class DoctorLoginInput(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class DoctorVerificationInfo(BaseModel):
    verified: bool = False
    verified_at: Optional[datetime] = None
    reg_number: Optional[str] = None
    state_council: Optional[str] = None
    year: Optional[str] = None
    qualification: Optional[str] = None
    status: Optional[str] = None
    cached: bool = False  # true when served from our cache, not a live call
    source: Optional[str] = None  # e.g. "api.askmydoc.in (NMC IMR)"


class DoctorProfile(BaseModel):
    id: int
    full_name: str
    email: str
    reg_number: str
    state_council: Optional[str] = None
    reg_year: Optional[str] = None
    specialization: Optional[str] = None
    qualification: Optional[str] = None
    phone: Optional[str] = None
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    verification: DoctorVerificationInfo
    appointment_count: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DoctorAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    profile: DoctorProfile


class DoctorReverifyInput(BaseModel):
    force_refresh: bool = True
