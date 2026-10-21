"""
Doctor account — client/server authenticated portal user.

Verification source: the free NMC Indian Medical Register proxy at
https://api.askmydoc.in (no API key). The raw IMR payload returned at
registration is persisted on the row (`verification_json`) plus a
`verified_at` timestamp so the portal can render "NMC verified" instantly
without re-hitting the external API on every request; a short in-memory
TTL cache in app.services.askmydoc debounces repeat lookups.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from app.database.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)

    # Account credentials (client/server login, JWT-issued on /doctor/auth/login)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # bcrypt hash via app.auth.security

    # NMC Indian Medical Register identity (verified through api.askmydoc.in)
    reg_number = Column(String, unique=True, index=True, nullable=False)
    state_council = Column(String, nullable=True)
    reg_year = Column(String, nullable=True)

    # Verification cache — persisted at register/reverify time so the portal
    # never blocks on the external service for a returning doctor.
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    verification_json = Column(Text, nullable=True)  # raw IMR payload

    # Practice info (self-reported + hospital designation)
    specialization = Column(String, nullable=True)
    qualification = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    hospital_id = Column(
        Integer,
        ForeignKey("hospitals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
