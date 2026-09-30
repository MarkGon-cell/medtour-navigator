from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Float,
    DateTime,
    String,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.database import Base


class HospitalWaitingPrediction(Base):
    __tablename__ = "hospital_waiting_predictions"

    id = Column(Integer, primary_key=True, index=True)

    hospital_id = Column(
        BigInteger,
        ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )

    predicted_waiting_minutes = Column(
        Integer,
        nullable=True,
    )

    prediction_min_minutes = Column(
        Integer,
        nullable=True,
    )

    prediction_max_minutes = Column(
        Integer,
        nullable=True,
    )

    prediction_generated_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    model_version = Column(
        String,
        nullable=True,
    )

    confidence = Column(
        Float,
        nullable=True,
    )

    hospital = relationship("Hospital")