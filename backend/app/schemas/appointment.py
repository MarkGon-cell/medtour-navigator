from datetime import datetime
from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    hospital_id: int
    department: str | None = None
    appointment_time: datetime
    symptoms: str | None = None
    is_emergency: bool = False


class AppointmentResponse(BaseModel):
    id: int
    user_id: int
    hospital_id: int
    department: str | None = None
    appointment_time: datetime
    status: str
    symptoms: str | None = None
    is_emergency: bool
    check_in_time: datetime | None = None
    consultation_start_time: datetime | None = None

    created_at: datetime

    class Config:
        from_attributes = True