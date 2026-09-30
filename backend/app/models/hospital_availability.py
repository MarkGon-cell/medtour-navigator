from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.database import Base


class HospitalAvailability(Base):
    __tablename__ = "hospital_availability"

    id = Column(Integer, primary_key=True, index=True)

    hospital_id = Column(
        BigInteger,
        ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )

    available_general_beds = Column(Integer, nullable=True)
    available_icu_beds = Column(Integer, nullable=True)
    available_emergency_beds = Column(Integer, nullable=True)

    emergency_status = Column(String, nullable=True)

    source_type = Column(String, nullable=False)
    source_url = Column(String, nullable=True)

    observed_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    expires_at = Column(DateTime, nullable=True)

    confidence = Column(Float, nullable=True)

    hospital = relationship("Hospital")