from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)

    # Basic information
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    care_type = Column(String, nullable=True)
    discipline = Column(String, nullable=True)

    # Location
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=True, index=True)
    subdistrict = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    pincode = Column(String, nullable=True)

    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Medical information
    specialties = Column(Text, nullable=True)
    facilities = Column(Text, nullable=True)
    miscellaneous_facilities = Column(Text, nullable=True)

    # Emergency services
    emergency_available = Column(Boolean, default=False)
    emergency_services = Column(Text, nullable=True)
    emergency_phone = Column(String, nullable=True)
    ambulance_phone = Column(String, nullable=True)
    bloodbank_phone = Column(String, nullable=True)

    # Contact
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    tollfree = Column(String, nullable=True)
    helpline = Column(String, nullable=True)
    website = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # Hospital capacity
    total_beds = Column(Integer, nullable=True)
    private_wards = Column(Integer, nullable=True)
    economically_weaker_beds = Column(Integer, nullable=True)

    # Other information
    doctors = Column(Integer, nullable=True)
    medical_consultants = Column(Integer, nullable=True)
    established_year = Column(Integer, nullable=True)

    accreditation = Column(Text, nullable=True)
    registration_number = Column(String, nullable=True)
    empanelment = Column(Text, nullable=True)

    # Cost information from directory
    tariff_range = Column(Text, nullable=True)