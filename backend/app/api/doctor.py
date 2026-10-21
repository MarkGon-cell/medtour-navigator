"""
Doctor Portal Router — the diagnosis → QR → claim hand-off.

Storage contract: PostgreSQL keeps appointment STATUS and nothing else. The
diagnosis, prescription and notes the doctor types in are never written to a
table. They are minted into a QR image server-side, the patient scans that QR
into their own device, and from that moment they live in the patient's
localStorage and `.mtr` vault. The row only ever learns `is_completed` (the
scan matched) and `is_verified` (the patient paid to generate the claim PDF).

QR and PDF generation both happen here, in the backend — the browser never
draws a QR or lays out a PDF.
"""

import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.doctor_auth import get_current_doctor
from app.database.database import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.schemas.appointment import (
    AppointmentResponse,
    ClaimPurchaseInput,
    ClaimPurchaseResponse,
    ClaimRegenerateInput,
    DiagnosisInput,
    DiagnosisResponse,
    InvoiceInput,
    QrScanInput,
    QrScanResponse,
)
from app.services.claim_pdf import render_claim_pdf_base64, verification_url
from app.services.qr_service import build_diagnosis_payload, build_qr_png_base64


router = APIRouter(
    prefix="/doctor",
    tags=["Doctor Portal"],
)


# Test-mode price to generate the verified mediclaim PDF. Paid once — after
# that the PDF is free to re-download for the same appointment.
CLAIM_AMOUNT = 15.0
CLAIM_CURRENCY = "USD"


def _format_appointment(app: Appointment) -> dict:
    """
    The appointment as the portal renders it.

    Note what is absent: diagnosis, prescription, notes, invoice, and every
    lifecycle timestamp. None of it is stored, so none of it can be returned.
    `diagnosis_entered` (a doctor has been stamped on) and `qr_minted` (stage 2
    ran, so a discharge QR exists) are the only traces of the clinical step —
    they say the step happened, never what was in it.
    """
    hospital = app.hospital
    return {
        "id": app.id,
        "appointment_code": app.appointment_code,
        "patient_name": app.patient_name,
        "reason": app.reason,
        "status": app.status,
        "is_completed": app.is_completed,
        "is_verified": app.is_verified,
        "doctor_name": app.doctor_name,
        "hospital_id": app.hospital_id,
        "hospital_name": app.hospital_name,
        "department": app.department,
        "appointment_time": app.appointment_time,
        "created_at": app.created_at,
        "diagnosis_entered": bool(app.doctor_name),
        "qr_minted": bool(app.qr_minted),
        "hospital": {
            "id": hospital.id,
            "name": hospital.name,
            "city": hospital.city,
            "state": hospital.state,
            "address": hospital.address,
            "phone": hospital.phone,
            "emergency_phone": hospital.emergency_phone,
            "emergency_available": hospital.emergency_available,
            "latitude": hospital.latitude,
            "longitude": hospital.longitude,
        } if hospital else None,
    }


def _load_for_doctor(
    db: Session,
    doctor: Doctor,
    appointment_code: str,
) -> Appointment:
    """Fetch an appointment and enforce the hospital scope rule."""
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == appointment_code)
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=f"Appointment with code '{appointment_code}' not found.",
        )
    if doctor.hospital_id and appointment.hospital_id != doctor.hospital_id:
        raise HTTPException(
            status_code=403,
            detail="This appointment belongs to a different hospital.",
        )
    return appointment


def _verification_hash(appointment: Appointment) -> str:
    """
    Deterministic over the facts that identify this claim, so the same
    appointment always re-derives the identical hash on a re-download.
    """
    material = "|".join(
        [
            appointment.appointment_code or "",
            str(appointment.id),
            str(appointment.hospital_id),
            (appointment.doctor_name or "").strip().casefold(),
            appointment.appointment_time.isoformat()
            if appointment.appointment_time
            else "",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _claim_facts(
    db: Session,
    appointment: Appointment,
    diagnosis: Optional[str] = None,
    prescription: Optional[str] = None,
    diagnosis_notes: Optional[str] = None,
    invoice: Optional[dict] = None,
    patient: Optional[dict] = None,
) -> dict:
    """
    Assemble everything the claim PDF needs.

    The clinical trio, the doctor's stage-2 bill and the patient's identity
    block are all passed in, not read from the row — the server never stored
    any of them. The patient's device supplies them back from localStorage /
    the `.mtr` at the moment it asks for the PDF to be rendered.

    Two distinct amounts are reported and they are deliberately not merged:

      * `amount` / `currency` — the doctor's bill for the visit (stage 2),
        whatever total the doctor entered.
      * `report_fee` / `report_fee_currency` — the one-time $15 the patient
        pays to have this document generated at all.
    """
    hospital = appointment.hospital

    doctor = None
    if appointment.doctor_name:
        doctor = (
            db.query(Doctor)
            .filter(Doctor.full_name == appointment.doctor_name)
            .order_by(Doctor.verified.desc(), Doctor.id.desc())
            .first()
        )

    # Derived from the appointment id so the number is stable across
    # re-downloads — a fresh number each time would break any audit trail.
    derived_number = (
        f"MT-INV-{appointment.appointment_code.replace('MT-', '')}"
        if appointment.appointment_code
        else None
    )

    invoice = invoice or {}
    invoice_number = (invoice.get("invoice_number") or "").strip() or derived_number

    visit_invoice = {
        "invoice_number": invoice_number,
        "issued_on": invoice.get("issued_on"),
        "line_items": invoice.get("line_items") or [],
        "subtotal": invoice.get("subtotal"),
        "tax_amount": invoice.get("tax_amount"),
        "total_amount": invoice.get("total_amount"),
        "currency": (invoice.get("currency") or CLAIM_CURRENCY).upper(),
        "notes": invoice.get("notes"),
    }

    return {
        "success": True,
        "appointment_code": appointment.appointment_code,
        "is_verified": appointment.is_verified,
        "verification_hash": _verification_hash(appointment),
        "patient_name": appointment.patient_name,
        "patient": patient or None,
        "hospital_name": appointment.hospital_name or (hospital.name if hospital else None),
        "hospital_address": hospital.address if hospital else None,
        "department": appointment.department,
        "appointment_time": appointment.appointment_time,
        "reason": appointment.reason,
        "diagnosis": diagnosis,
        "prescription": prescription,
        "diagnosis_notes": diagnosis_notes,
        "doctor_name": doctor.full_name if doctor else appointment.doctor_name,
        "doctor_reg_number": doctor.reg_number if doctor else None,
        "doctor_state_council": doctor.state_council if doctor else None,
        "doctor_verified": bool(doctor.verified) if doctor else False,
        "doctor_verified_at": doctor.verified_at if doctor else None,
        "invoice_number": invoice_number,
        "invoice": visit_invoice,
        "amount": visit_invoice["total_amount"],
        "currency": visit_invoice["currency"],
        "report_fee": CLAIM_AMOUNT,
        "report_fee_currency": CLAIM_CURRENCY,
        "verification_url": verification_url(appointment.appointment_code),
    }


# ---------------------------------------------------------------------------
# Doctor: list appointments (all statuses)
# ---------------------------------------------------------------------------

@router.get("/appointments")
def list_doctor_appointments(
    hospital_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    """
    List appointments for the signed-in doctor's hospital. A doctor with no
    designated hospital sees every appointment (demo mode). The patient-facing
    scan and claim endpoints on this prefix stay public; this one does not.
    """
    query = db.query(Appointment)

    effective_hospital_id = doctor.hospital_id or hospital_id
    if effective_hospital_id:
        query = query.filter(Appointment.hospital_id == effective_hospital_id)

    if status:
        status_clean = status.strip().lower()
        if status_clean == "upcoming":
            query = query.filter(
                Appointment.status.in_(["upcoming", "booked", "in_consultation"])
            )
        elif status_clean == "completed":
            query = query.filter(
                Appointment.is_completed.is_(True)
            )
        elif status_clean == "cancelled":
            query = query.filter(Appointment.status == "cancelled")

    appointments = query.order_by(Appointment.appointment_time.desc()).all()
    return [_format_appointment(a) for a in appointments]


# ---------------------------------------------------------------------------
# Doctor: submit diagnosis + bill → mint the QR
# ---------------------------------------------------------------------------

def _normalise_invoice(invoice, appointment_code: str) -> dict:
    """
    Canonical form of the doctor's stage-2 bill.

    Totals are recomputed from the line items so the table printed in the PDF
    can never disagree with the amount printed beside it, and the invoice
    number defaults to one derived from the appointment code — stable across
    re-downloads, which any audit trail depends on.
    """
    number = (invoice.invoice_number or "").strip()
    if not number:
        number = f"MT-INV-{appointment_code.replace('MT-', '')}"

    return {
        "invoice_number": number,
        "issued_on": (invoice.issued_on or "").strip() or None,
        "line_items": [
            {
                "description": li.description,
                "quantity": float(li.quantity or 0),
                "unit_price": float(li.unit_price or 0),
            }
            for li in invoice.line_items
        ],
        "subtotal": invoice.computed_subtotal(),
        "tax_amount": round(float(invoice.tax_amount or 0.0), 2),
        "total_amount": invoice.computed_total(),
        "currency": (invoice.currency or "USD").upper(),
        "notes": (invoice.notes or "").strip() or None,
    }


@router.post("/diagnosis", response_model=DiagnosisResponse)
def submit_diagnosis(
    payload: DiagnosisInput,
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    """
    Two-stage discharge entry.

    **Stage 1** — diagnosis, prescription, notes (no `invoice`): the doctor is
    stamped onto the row and the visit moves into consultation. No QR exists
    yet, so `qr_payload` and `qr_image_base64` come back null.

    **Stage 2** — the same body *with* `invoice`: the bill is validated,
    `qr_minted` flips true, and the QR is rendered server-side carrying the
    clinical trio **and** the invoice.

    Nothing clinical or financial is ever persisted. It is packed into the QR
    payload; the patient scans the QR, and that is the only way any of it ever
    reaches their device.
    """
    appointment = _load_for_doctor(db, doctor, payload.appointment_code)

    if appointment.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Cannot enter diagnosis for a cancelled appointment.",
        )

    diagnosis = (payload.diagnosis or "").strip()
    prescription = (payload.prescription or "").strip()
    if not diagnosis:
        raise HTTPException(
            status_code=400,
            detail="A diagnosis is required before the QR can be generated.",
        )

    invoice = payload.invoice
    invoice_dict = None
    if invoice is not None:
        invoice_dict = _normalise_invoice(invoice, appointment.appointment_code)
        if invoice_dict["total_amount"] <= 0 and not invoice_dict["line_items"]:
            raise HTTPException(
                status_code=400,
                detail="Add at least one line item or a bill total before "
                "generating the QR.",
            )

    appointment.doctor_name = doctor.full_name
    if appointment.status in ("upcoming", "booked"):
        appointment.status = "in_consultation"
    if invoice_dict is not None:
        appointment.qr_minted = True
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    common = dict(
        appointment_code=appointment.appointment_code,
        status=appointment.status,
        diagnosis=diagnosis,
        prescription=prescription,
        diagnosis_notes=(payload.diagnosis_notes or "").strip() or None,
    )

    # Stage 1: the clinical step landed, but there is nothing to scan yet.
    if invoice_dict is None:
        return DiagnosisResponse(
            **common,
            stage="clinical",
            qr_minted=bool(appointment.qr_minted),
            invoice=None,
            qr_payload=None,
            qr_image_base64=None,
        )

    # Stage 2: mint the QR carrying the clinical trio AND the bill.
    qr_payload = build_diagnosis_payload(
        appointment_code=appointment.appointment_code,
        appointment_id=appointment.id,
        diagnosis=diagnosis,
        prescription=prescription,
        diagnosis_notes=(payload.diagnosis_notes or "").strip() or None,
        invoice=invoice_dict,
    )

    return DiagnosisResponse(
        **common,
        stage="invoiced",
        qr_minted=True,
        invoice=InvoiceInput(**invoice_dict),
        qr_payload=qr_payload,
        qr_image_base64=build_qr_png_base64(qr_payload),
    )


# ---------------------------------------------------------------------------
# Doctor: re-mint the QR for an appointment already diagnosed
# ---------------------------------------------------------------------------

@router.post("/qr", response_model=DiagnosisResponse)
def regenerate_qr(
    payload: DiagnosisInput,
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    """
    Re-render the QR for a visit already diagnosed.

    Because neither the clinical text nor the invoice was ever stored, the
    doctor's browser holds them (localStorage) and sends them back here
    whenever the QR needs redrawn — a page reload, a new tab, or simply
    showing it again to the patient. The invoice is therefore mandatory here:
    without it this would only be stage 1 and there would be no QR to draw.
    """
    if payload.invoice is None:
        raise HTTPException(
            status_code=400,
            detail="A QR redraw needs the full discharge record: clinical "
            "detail and the stage-2 invoice.",
        )
    return submit_diagnosis(payload=payload, doctor=doctor, db=db)


# ---------------------------------------------------------------------------
# Doctor: get a single appointment by its code
# ---------------------------------------------------------------------------

@router.get("/appointment/{appointment_code}")
def get_appointment_by_code(
    appointment_code: str,
    doctor: Doctor = Depends(get_current_doctor),
    db: Session = Depends(get_db),
):
    appointment = _load_for_doctor(db, doctor, appointment_code)
    return _format_appointment(appointment)


# ---------------------------------------------------------------------------
# Patient: scan the QR → match the code → mark completed
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=QrScanResponse)
def scan_qr_code(
    payload: QrScanInput,
    db: Session = Depends(get_db),
):
    """
    The patient scans the doctor's QR from the Visits page.

    The payload is JSON:
        {"code":"MT-XXXXXXXX","id":<appointment id>,"dx":"...","rx":"..."}

    The visit is marked completed ONLY when the appointment code on the QR
    matches the appointment that code resolves to. Any mismatch — unknown
    code, or an id that belongs to a different appointment — returns
    success=False with human-readable `notes` explaining why nothing was
    checked in. Nothing is written in that case.

    Note the diagnosis rides back inside the same payload: the patient's
    device stores it locally, because the server never did.
    """
    import json as _json

    raw = (payload.qr_payload or "").strip()

    appointment_code = None
    qr_appointment_id = None
    try:
        parsed = _json.loads(raw)
        if isinstance(parsed, dict):
            appointment_code = parsed.get("code") or parsed.get("appointment_code")
            raw_id = parsed.get("id") or parsed.get("appointment_id")
            if raw_id is not None:
                try:
                    qr_appointment_id = int(raw_id)
                except (TypeError, ValueError):
                    qr_appointment_id = None
    except (ValueError, _json.JSONDecodeError):
        appointment_code = raw  # not JSON — treat the raw string as the code

    if not appointment_code:
        return QrScanResponse(
            success=False,
            message="Appointment not checked in.",
            notes="This QR code does not contain a MedTour appointment code. "
            "Ask your doctor to regenerate the QR from the Doctor Portal.",
        )

    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == appointment_code)
        .first()
    )

    if not appointment:
        return QrScanResponse(
            success=False,
            message="Appointment not checked in.",
            notes=f"No appointment was found for code '{appointment_code}'. "
            "The QR may be expired, belong to a different patient, or was not "
            "issued by this hospital.",
        )

    # The appointment id on the QR must match the one the code resolves to.
    if qr_appointment_id is not None and qr_appointment_id != appointment.id:
        return QrScanResponse(
            success=False,
            message="Appointment not checked in.",
            notes=f"Appointment id mismatch: this QR code belongs to appointment "
            f"#{qr_appointment_id}, but code '{appointment_code}' resolves to "
            f"appointment #{appointment.id}. Scanning was refused so the wrong "
            "visit could not be checked in.",
        )

    if appointment.is_completed:
        return QrScanResponse(
            success=True,
            message="This appointment is already marked completed.",
            notes=None,
            appointment=_format_appointment(appointment),
        )

    # Match confirmed — this is the only place the completed flag is set.
    appointment.is_completed = True
    appointment.status = "completed"
    appointment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(appointment)

    return QrScanResponse(
        success=True,
        message="Appointment verified and marked as completed.",
        notes=None,
        appointment=_format_appointment(appointment),
    )


# ---------------------------------------------------------------------------
# Patient: pay once → backend renders the password-protected PDF
# ---------------------------------------------------------------------------

@router.post("/claim/purchase", response_model=ClaimPurchaseResponse)
def purchase_claim(
    payload: ClaimPurchaseInput,
    db: Session = Depends(get_db),
):
    """
    Pay (test mode) to generate the verified mediclaim PDF.

    Sets `is_verified` on the appointment — "is verified" only becomes true
    after this payment — and hands the claim facts plus the rendered PDF back
    in one response. The clinical text comes from the patient's own device
    because it was never stored server-side; the server uses it only to lay
    out the document.

    The PDF is password-protected with the patient's `.mtr` passphrase, so the
    document can only be opened by whoever could open the vault it came from.
    """
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == payload.appointment_code)
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=f"Appointment with code '{payload.appointment_code}' not found.",
        )
    if not appointment.is_completed:
        raise HTTPException(
            status_code=400,
            detail="Claim can only be generated for a completed appointment.",
        )
    if not (payload.mtr_password or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A password is required to protect the claim PDF.",
        )

    # Test-mode payment: always succeeds. One-time — a repeat call is a
    # re-download, not a second charge, so this only ever flips once.
    if not appointment.is_verified:
        appointment.is_verified = True
        appointment.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)

    facts = _claim_facts(
        db,
        appointment,
        diagnosis=(payload.diagnosis or "").strip() or None,
        prescription=(payload.prescription or "").strip() or None,
        diagnosis_notes=(payload.diagnosis_notes or "").strip() or None,
        invoice=payload.invoice.model_dump() if payload.invoice else None,
        patient=payload.patient.model_dump() if payload.patient else None,
    )
    facts["claim_purchased_at"] = appointment.updated_at
    facts["pdf_base64"] = render_claim_pdf_base64(facts, payload.mtr_password)
    facts["message"] = (
        "Payment successful (test mode). Verified mediclaim PDF unlocked — "
        "it is now free to re-download for this appointment."
    )
    return ClaimPurchaseResponse(**facts)


# ---------------------------------------------------------------------------
# Patient: re-download after the one-time purchase
# ---------------------------------------------------------------------------

@router.post("/claim/pdf", response_model=ClaimPurchaseResponse)
def download_claim_pdf(
    payload: ClaimRegenerateInput,
    db: Session = Depends(get_db),
):
    """
    Re-render the PDF for an appointment already paid for.

    No second charge: `is_verified` is already true, so this only rebuilds the
    document from the facts the patient's device supplies. The password still
    has to be sent because the PDF is re-encrypted every time it is rendered.
    """
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == payload.appointment_code)
        .first()
    )
    if not appointment:
        raise HTTPException(
            status_code=404,
            detail=f"Appointment with code '{payload.appointment_code}' not found.",
        )
    if not appointment.is_verified:
        raise HTTPException(
            status_code=400,
            detail="This claim has not been purchased yet.",
        )
    if not (payload.mtr_password or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A password is required to protect the claim PDF.",
        )

    facts = _claim_facts(
        db,
        appointment,
        diagnosis=(payload.diagnosis or "").strip() or None,
        prescription=(payload.prescription or "").strip() or None,
        diagnosis_notes=(payload.diagnosis_notes or "").strip() or None,
        invoice=payload.invoice.model_dump() if payload.invoice else None,
        patient=payload.patient.model_dump() if payload.patient else None,
    )
    facts["claim_purchased_at"] = appointment.updated_at
    facts["pdf_base64"] = render_claim_pdf_base64(facts, payload.mtr_password)
    facts["message"] = "Claim PDF regenerated."
    return ClaimPurchaseResponse(**facts)


# ---------------------------------------------------------------------------
# Patient: claim status (no PDF) — cheap check before offering a download
# ---------------------------------------------------------------------------

@router.get("/claim/{appointment_code}", response_model=ClaimPurchaseResponse)
def get_claim_status(
    appointment_code: str,
    db: Session = Depends(get_db),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.appointment_code == appointment_code)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    facts = _claim_facts(db, appointment)
    facts["claim_purchased_at"] = appointment.updated_at
    facts["message"] = "Claim status retrieved."
    return ClaimPurchaseResponse(**facts)
