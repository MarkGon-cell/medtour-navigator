from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False)

    address = Column(Text, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    specialties = Column(Text, nullable=True)
    languages = Column(Text, nullable=True)

    consultation_fee = Column(Float, nullable=True)
    waiting_time = Column(Integer, nullable=True)

    emergency_available = Column(Boolean, default=False)
    icu_available = Column(Boolean, default=False)

    rating = Column(Float, nullable=True)
    phone = Column(String, nullable=True)