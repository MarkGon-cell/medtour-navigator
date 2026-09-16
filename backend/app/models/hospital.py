from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)

    # Basic information
    name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=True, index=True)
    address = Column(Text, nullable=True)
    pincode = Column(String, nullable=True)

    # Geographic information
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Medical information
    specialties = Column(Text, nullable=True)
    facilities = Column(Text, nullable=True)

    # Emergency information
    emergency_available = Column(Boolean, default=False)
    emergency_services = Column(Text, nullable=True)
    ambulance_phone = Column(String, nullable=True)

    # Contact
    phone = Column(String, nullable=True)
    website = Column(String, nullable=True)

    # Hospital information
    total_beds = Column(Integer, nullable=True)
    tariff_range = Column(Text, nullable=True)