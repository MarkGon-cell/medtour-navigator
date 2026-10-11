from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class AppointmentCreate(BaseModel):
    hospital_id: int
    department: Optional[str] = None
    appointment_time: datetime
    symptoms: Optional[str] = None
    is_emergency: bool = False


class AppointmentStatusUpdate(BaseModel):
    status: str


class AppointmentHospitalSummary(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    state: str
    address: Optional[str] = None
    phone: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_available: Optional[bool] = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class AppointmentResponse(BaseModel):
    id: int
    user_id: int
    hospital_id: int
    department: Optional[str] = None
    appointment_time: datetime
    status: str
    symptoms: Optional[str] = None
    is_emergency: bool
    check_in_time: Optional[datetime] = None
    consultation_start_time: Optional[datetime] = None
    created_at: datetime
    hospital: Optional[AppointmentHospitalSummary] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True
