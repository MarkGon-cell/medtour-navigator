from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.sql import func
from app.database.database import Base


class CuratedHospital(Base):
    """
    Curated Hospital table created from existing hospital directory data,
    structured with clean location, contact, and metadata fields,
    plus enrichment fields populated by Google AI Mode research.
    """
    __tablename__ = "curated_hospitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_hospital_id = Column(Integer, nullable=True, index=True)

    # Core identification & location from original hospital data
    name = Column(String, nullable=False, index=True)
    address = Column(Text, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=True)
    pincode = Column(String, nullable=True, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Contact & emergency (carried over from existing directory)
    phone = Column(String, nullable=True)
    emergency_phone = Column(String, nullable=True)
    website = Column(String, nullable=True)
    emergency_available = Column(Boolean, default=False)

    # --- New Columns for AI Mode Enrichment ---
    speciality = Column(Text, nullable=True)            # Medical specialties / disciplines
    tier = Column(String, nullable=True)                  # e.g., "Tier 1 - Multi-Speciality Tertiary", "Tier 2", "Primary Care Clinic"
    rating = Column(Float, nullable=True)                # Rating (e.g., 4.5)
    services = Column(Text, nullable=True)               # Clinical services, diagnostics, surgeries
    amenities = Column(Text, nullable=True)              # Cashless insurance, private rooms, cafeteria, ICU, pharmacy

    # AI Mode Enrichment status & provenance
    ai_enriched = Column(Boolean, default=False, nullable=False)
    ai_enriched_at = Column(DateTime(timezone=True), nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
