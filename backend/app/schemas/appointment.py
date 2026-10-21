from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AppointmentCreate(BaseModel):
    """
    Booking payload. There are no patient accounts: the client sends the
    patient's name and reason straight from the docked `.mtr` medical profile
    (booking is disabled in the UI when no `.mtr` is docked) and the server
    mints the unique appointment id the whole flow keys on.
    """
    hospital_id: int
    patient_name: str
    reason: str
    department: Optional[str] = None
    appointment_time: datetime


class AppointmentHospitalSummary(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    state: str
    address: Optional[str] = None
    phone: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_available: Optional[bool] = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class AppointmentResponse(BaseModel):
    """
    The appointment row as the portal and the visits ledger read it.

    There is deliberately no diagnosis / prescription / notes here: clinical
    data is volatile and travels inside the QR payload to the patient's own
    device. `is_completed` is what a successful scan sets; `is_verified` is
    what a paid claim generation sets.
    """
    id: int
    appointment_code: str
    patient_name: str
    reason: Optional[str] = None
    status: str
    is_completed: bool = False
    is_verified: bool = False
    doctor_name: Optional[str] = None
    hospital_id: int
    hospital_name: Optional[str] = None
    department: Optional[str] = None
    appointment_time: datetime
    created_at: datetime

    # Convenience flags: a doctor has been stamped on the row, and the
    # discharge QR has actually been minted (stage 2 of the doctor's flow).
    diagnosis_entered: bool = False
    qr_minted: bool = False

    hospital: Optional[AppointmentHospitalSummary] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Diagnosis -> QR (the doctor's discharge hand-off)
# ---------------------------------------------------------------------------

class InvoiceLineItem(BaseModel):
    """One billable row on the doctor's visit invoice."""
    description: str
    quantity: float = 1.0
    unit_price: float = 0.0


class InvoiceInput(BaseModel):
    """
    Stage 2 of the doctor's flow: the bill for THIS visit.

    Entered after the clinical trio and sent inside the QR, exactly like the
    diagnosis — so it is never written to the row either. Totals are echoed
    back rather than trusted, and a total is recomputed from the line items
    whenever they are supplied.
    """
    invoice_number: Optional[str] = None
    issued_on: Optional[str] = None
    line_items: list[InvoiceLineItem] = []
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    currency: str = "USD"
    notes: Optional[str] = None

    def computed_total(self) -> float:
        """Line items win over a hand-typed total so the PDF cannot disagree
        with its own table."""
        if self.line_items:
            subtotal = sum(
                float(li.quantity or 0) * float(li.unit_price or 0)
                for li in self.line_items
            )
            tax = float(self.tax_amount or 0.0)
            return round(subtotal + tax, 2)
        try:
            return round(float(self.total_amount or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0

    def computed_subtotal(self) -> float:
        if self.line_items:
            return round(
                sum(
                    float(li.quantity or 0) * float(li.unit_price or 0)
                    for li in self.line_items
                ),
                2,
            )
        try:
            return round(float(self.subtotal or 0.0), 2)
        except (TypeError, ValueError):
            return 0.0


class PatientProfileInput(BaseModel):
    """
    The patient's identity block, read off their own `.mtr` at claim time.

    None of it is stored — it rides the request so the PDF can carry the same
    passport / insurance / allergy information an insurer actually needs.
    """
    full_name: Optional[str] = None
    passport_no: Optional[str] = None
    national_id_no: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    medications: Optional[str] = None
    insurance_policy_no: Optional[str] = None
    insurance_provider: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None


class DiagnosisInput(BaseModel):
    """
    What the doctor types in. This is NEVER persisted — it goes straight into
    the QR the server mints, and from there into the patient's device.

    Two stages share this body: submitting without an `invoice` is stage 1
    (clinical only, no QR yet); supplying the invoice is stage 2, which is
    what mints the QR.
    """
    appointment_code: str
    diagnosis: str
    prescription: str
    diagnosis_notes: Optional[str] = None
    invoice: Optional[InvoiceInput] = None


class DiagnosisResponse(BaseModel):
    """
    Diagnosis is echoed back (the doctor still has it on their screen) along
    with the appointment code.

    `stage == "clinical"` means only stage 1 landed: the doctor is recorded
    on the row, but no QR exists yet, so both QR fields are null. Stage 2
    (`invoice` present) returns the QR payload string and the QR image itself
    as base64 PNG — generated server-side, not in the browser.
    """
    appointment_code: str
    status: str
    stage: str
    qr_minted: bool
    diagnosis: str
    prescription: str
    diagnosis_notes: Optional[str] = None
    invoice: Optional[InvoiceInput] = None
    qr_payload: Optional[str] = None
    qr_image_base64: Optional[str] = None


class QrScanInput(BaseModel):
    """Patient scans the QR the doctor's portal is showing."""
    qr_payload: str


class QrScanResponse(BaseModel):
    """
    `success=False` still returns HTTP 200 so the client can render the
    human-readable `notes` explaining exactly why the appointment was NOT
    checked in (code mismatch, appointment id mismatch, unknown code, ...).
    """
    success: bool
    message: str
    notes: Optional[str] = None
    appointment: Optional[AppointmentResponse] = None


# ---------------------------------------------------------------------------
# Verified mediclaim claim
# ---------------------------------------------------------------------------

class ClaimPurchaseInput(BaseModel):
    """
    The patient pays once to unlock the verified PDF. Everything volatile is
    sent from the patient's own device (localStorage / `.mtr`) because none of
    it was ever stored server-side; the server uses it only to render the PDF.
    """
    appointment_code: str
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    diagnosis_notes: Optional[str] = None
    # The doctor's stage-2 bill, recovered from the QR the patient scanned.
    invoice: Optional[InvoiceInput] = None
    # The patient's own identity block from their `.mtr`.
    patient: Optional[PatientProfileInput] = None
    # The `.mtr` passphrase — the PDF is password-protected with it.
    mtr_password: str


class ClaimRegenerateInput(BaseModel):
    """Re-download after a one-time purchase already happened."""
    appointment_code: str
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    diagnosis_notes: Optional[str] = None
    invoice: Optional[InvoiceInput] = None
    patient: Optional[PatientProfileInput] = None
    mtr_password: str


class ClaimPurchaseResponse(BaseModel):
    """
    Everything the patient's device needs after paying: the claim facts, the
    verification hash that backs the PDF's QR, and the rendered PDF itself as
    base64. The PDF was produced by the backend — the browser never builds it.
    """
    success: bool
    message: str
    appointment_code: str
    is_verified: bool
    claim_purchased_at: Optional[datetime] = None
    verification_hash: Optional[str] = None

    # Patient operated on
    patient_name: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    department: Optional[str] = None
    appointment_time: Optional[datetime] = None
    reason: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    diagnosis_notes: Optional[str] = None

    # Operating doctor + their verification status (drives the PDF's QR)
    doctor_name: Optional[str] = None
    doctor_reg_number: Optional[str] = None
    doctor_state_council: Optional[str] = None
    doctor_verified: bool = False
    doctor_verified_at: Optional[datetime] = None

    # Invoice — both the doctor's visit bill and the one-time report fee,
    # because the PDF prints both and the client needs them to redisplay the
    # full documentation without re-deriving anything.
    invoice_number: Optional[str] = None
    invoice: Optional[dict] = None
    patient: Optional[dict] = None
    amount: Optional[float] = None
    currency: Optional[str] = "USD"
    report_fee: Optional[float] = None
    report_fee_currency: Optional[str] = None

    # Where the QR at the bottom of the PDF points, and the rendered PDF.
    verification_url: Optional[str] = None
    pdf_base64: Optional[str] = None
