from pydantic import BaseModel
from typing import Optional


class HospitalBase(BaseModel):
    name: str
    city: Optional[str] = None
    state: str
    district: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None

    latitude: float
    longitude: float

    specialties: Optional[str] = None
    facilities: Optional[str] = None

    emergency_available: bool = False
    emergency_services: Optional[str] = None
    ambulance_phone: Optional[str] = None

    phone: Optional[str] = None
    website: Optional[str] = None

    total_beds: Optional[int] = None
    tariff_range: Optional[str] = None


class HospitalCreate(HospitalBase):
    pass


class HospitalResponse(HospitalBase):
    id: int

    class Config:
        from_attributes = True