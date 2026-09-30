from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    hospital_id = Column(
        BigInteger,
        ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )

    department = Column(
        String,
        nullable=True,
        index=True,
    )

    appointment_time = Column(
        DateTime,
        nullable=False,
    )

    status = Column(
        String,
        nullable=False,
        default="booked",
    )

    symptoms = Column(
        Text,
        nullable=True,
    )
    is_emergency = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    check_in_time = Column(
        DateTime,
        nullable=True,
    )

    consultation_start_time = Column(
        DateTime,
        nullable=True,
    )

    consultation_end_time = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    hospital = relationship("Hospital")