from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class HospitalQueueStatus(Base):
    __tablename__ = "hospital_queue_status"

    id = Column(Integer, primary_key=True, index=True)

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

    queue_size = Column(
        Integer,
        nullable=False,
        default=0,
    )

    emergency_cases = Column(
        Integer,
        nullable=False,
        default=0,
    )

    available_doctors = Column(
        Integer,
        nullable=False,
        default=0,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    source = Column(
    String,
    nullable=False,
    default="medtour_appointment"
    )

    hospital = relationship("Hospital")