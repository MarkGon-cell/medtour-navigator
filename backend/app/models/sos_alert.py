from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class SOSAlert(Base):
    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    user_name = Column(String, nullable=True)
    email = Column(String, nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String, nullable=False)
    pincode = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    contact_emergency_services = Column(Boolean, default=True, nullable=False)

    # Status: PENDING, DISPATCHED, RESOLVED, CANCELLED
    status = Column(String, default="PENDING", nullable=False, index=True)
    log_path = Column(String, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", lazy="joined")
