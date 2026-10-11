from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from app.database.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True)

    # Basic information
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    care_type = Column(String, nullable=True)
    discipline = Column(String, nullable=True)

    # Location
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=True, index=True)
    subdistrict = Column(String, nullable=True)
    address = Column(Text, nullable=True)
    pincode = Column(String, nullable=True)

    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)

    # Medical information
    specialties = Column(Text, nullable=True)
    facilities = Column(Text, nullable=True)
    miscellaneous_facilities = Column(Text, nullable=True)

    # Emergency services
    emergency_available = Column(Boolean, default=False)
    emergency_services = Column(Text, nullable=True)
    emergency_phone = Column(String, nullable=True)
    ambulance_phone = Column(String, nullable=True)
    bloodbank_phone = Column(String, nullable=True)

    # Contact
    phone = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    tollfree = Column(String, nullable=True)
    helpline = Column(String, nullable=True)
    website = Column(String, nullable=True)
    email = Column(String, nullable=True)

    # Hospital capacity
    total_beds = Column(Integer, nullable=True)
    private_wards = Column(Integer, nullable=True)
    economically_weaker_beds = Column(Integer, nullable=True)

    # Other information
    doctors = Column(Integer, nullable=True)
    medical_consultants = Column(Integer, nullable=True)
    established_year = Column(Integer, nullable=True)

    accreditation = Column(Text, nullable=True)
    registration_number = Column(String, nullable=True)
    empanelment = Column(Text, nullable=True)

    # Cost information from directory
    tariff_range = Column(Text, nullable=True)

    # --- Provenance & enrichment added by GET /hospitals/discover ---------
    # `source` records who owns the row: 'csv_import' for the national
    # directory load, otherwise the provider that discovered it ('overpass',
    # 'geoapify'). The CSV importer rebuilds this table from a DataFrame that
    # has no such column, so main.py re-adds these three idempotently on every
    # startup -- see _ensure_discovery_columns().
    source = Column(String, nullable=False, default="csv_import", server_default="csv_import")

    # Provider-native id (e.g. 'osm/way/123456', a Geoapify place_id). Lets a
    # repeat search recognise a facility it already stored even if the mapped
    # name changed or the coordinates drifted slightly.
    external_id = Column(String, nullable=True, index=True)

    # OSM opening_hours, stored so the UI can render a truthful 'Open Now'
    # badge. Never invent this string; absent means absent.
    opening_hours = Column(String, nullable=True)

    # --- Reputation (nullable by design) ---------------------------------
    # The national directory carries no user-generated ratings, so these stay
    # NULL until a real source (Google Places, Practo, etc.) loads them. When
    # NULL the UI must NOT invent stars -- it shows an inferred reputation
    # derived from name/accreditation/facilities instead. See
    # app.api.ai_analysis.infer_reputation.
    rating = Column(Float, nullable=True)         # 0.0 - 5.0, real source only
    review_count = Column(Integer, nullable=True)  # real source only