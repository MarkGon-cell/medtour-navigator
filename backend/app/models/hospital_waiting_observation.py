from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class HospitalWaitingObservation(Base):
    __tablename__ = "hospital_waiting_observations"

    id = Column(Integer, primary_key=True, index=True)

    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )

    department = Column(String, nullable=True, index=True)

    appointment_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    check_in_time = Column(
        DateTime,
        nullable=True,
    )

    consultation_start_time = Column(
        DateTime,
        nullable=True,
    )

    waiting_minutes = Column(
        Integer,
        nullable=True,
    )

    queue_size = Column(
        Integer,
        nullable=True,
    )

    emergency_cases = Column(
        Integer,
        nullable=True,
    )

    available_doctors = Column(
        Integer,
        nullable=True,
    )

    observed_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    source = Column(
        String,
        nullable=False,
        default="medtour_system",
    )

    hospital = relationship("Hospital")