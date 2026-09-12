from pydantic import BaseModel
from typing import Optional


class HospitalBase(BaseModel):
    name: str
    city: str
    state: str
    address: str

    latitude: float
    longitude: float

    specialties: Optional[str] = None
    languages: Optional[str] = None

    consultation_fee: Optional[float] = None
    waiting_time: Optional[int] = None

    emergency_available: bool = False
    icu_available: bool = False

    rating: Optional[float] = None
    phone: Optional[str] = None


class HospitalCreate(HospitalBase):
    pass


class HospitalResponse(HospitalBase):
    id: int

    class Config:
        from_attributes = True