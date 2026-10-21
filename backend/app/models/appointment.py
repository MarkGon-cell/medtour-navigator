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
    """
    The appointment workflow row — deliberately thin.

    PostgreSQL holds only hospital data, doctor data, SOS logs and appointment
    STATUS. Concretely this table is:

        unique appointment id, name, reason, is_completed, is_verified,
        doctor name, hospital name, date + time

    Clinical detail (diagnosis, prescription, notes) and billing detail are
    NEVER written here. The doctor enters them, the server mints a QR that
    carries them, the patient scans the QR into their own device, and that is
    where they live — localStorage plus the `.mtr` vault. Nothing on this row
    can leak a diagnosis because the row never had one.

    `is_completed` flips true when the patient scans the doctor's QR and the
    appointment code on the QR matches the appointment the code resolves to.
    `is_verified` flips true only after the patient pays (once) to generate the
    verified mediclaim PDF.
    """

    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)

    # The unique, human-readable appointment id the whole flow keys on
    # (MT-XXXXXXXX). Appears on the portal, in the QR, and in the PDF.
    appointment_code = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    # Row labels the doctor's portal has to show: who and why. These are not
    # accounts — there are no patient accounts in this system, only doctors.
    patient_name = Column(
        String,
        nullable=False,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    # Lifecycle for the portal's Upcoming / In Consultation / Completed tabs.
    # `is_completed` below is the durable flag the flow cares about; this
    # string is what the tab filters bind to.
    status = Column(
        String,
        nullable=False,
        default="upcoming",
        index=True,
    )

    # True once the appointment code on the doctor's QR matched on scan.
    is_completed = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # True once the patient has paid to generate the verified mediclaim PDF.
    # "Is verified" stays false until that payment happens.
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # True once stage 2 of the doctor's flow has run — clinical + invoice
    # submitted together, discharge QR minted. Stage 1 alone (doctor stamped,
    # no invoice) leaves this false, so the portal can tell "started" from
    # "ready to scan" without storing anything clinical.
    qr_minted = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    doctor_name = Column(
        String,
        nullable=True,
    )

    hospital_id = Column(
        BigInteger,
        ForeignKey("hospitals.id"),
        nullable=False,
        index=True,
    )

    # Denormalised so the row carries the hospital name on its own, exactly as
    # the portal and the claim PDF read it.
    hospital_name = Column(
        String,
        nullable=True,
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

    hospital = relationship("Hospital", lazy="joined")
