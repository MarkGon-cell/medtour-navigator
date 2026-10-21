from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Text,
    Boolean,
)

from app.database.database import Base


class SOSAlert(Base):
    """
    Anonymous SOS log.

    Deliberately holds NO user identity (no account, name, or email — there
    are no patient accounts at all). What it keeps is the operational payload
    an emergency responder needs: where the call came from, the message, and
    where it sits in the dispatch lifecycle.
    """

    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)

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
