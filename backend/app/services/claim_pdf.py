"""
Backend-side rendering of the verified mediclaim PDF.

The browser never builds this document. The patient's device sends the claim
facts it holds (localStorage / `.mtr`) plus the `.mtr` passphrase, and this
module produces the finished, password-protected PDF bytes.

Layout contract (see the product spec):

    MedTour letterhead
    Structured sections: patient / doctor / hospital / clinical / invoice
    QR code at the bottom + a verification link beside it
    PDF itself is password-protected with the patient's `.mtr` passphrase

The QR encodes a verification URL of the form
`{base}/verificationStatus?aid={appointment_code}` — the same link printed
next to it, so scanning and tapping land on the identical status page showing
the operating doctor's verification, the hospital, the patient, and a
verified badge.
"""

import base64
import io
import os

import qrcode
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption

load_dotenv()

# Where the QR / printed link resolve. Default is the local dev server so a
# scanned QR lands on something that actually answers. Point it at the
# machine's LAN address (e.g. http://192.168.1.20:8080) to scan from a phone,
# or at the deployed host in production.
VERIFICATION_BASE_URL = os.getenv(
    "VERIFICATION_BASE_URL",
    "http://localhost:8080",
).rstrip("/")

BRAND = colors.HexColor("#0F766E")
BRAND_LIGHT = colors.HexColor("#ECFDF5")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
RULE = colors.HexColor("#E5E7EB")
ALERT = colors.HexColor("#065F46")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def verification_url(appointment_code: str) -> str:
    """The link printed beside the QR and encoded inside it."""
    return f"{VERIFICATION_BASE_URL}/verificationStatus?aid={appointment_code}"


def build_verification_qr(url: str):
    """
    Render the verification QR as a real PIL image.

    `qrcode.make()` hands back a thin wrapper; reportlab's ImageReader needs
    the underlying PIL image, which the wrapper keeps on `_img`. Everything
    stays in memory — the QR never touches disk.
    """
    return qrcode.make(url, box_size=8, border=2)._img


def build_verification_qr_png(url: str) -> bytes:
    """Render the verification QR as PNG bytes."""
    buf = io.BytesIO()
    build_verification_qr(url).save(buf, format="PNG")
    return buf.getvalue()


def _fmt_dt(value) -> str:
    if not value:
        return "—"
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%d %b %Y, %H:%M UTC")
        except Exception:
            pass
    return str(value)


def _money(amount, currency: str = "USD") -> str:
    # `None` means the field was never supplied — print a dash, never "$None".
    if amount is None:
        return "—"
    symbol = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(
        (currency or "USD").upper(), ""
    )
    try:
        return f"{symbol}{float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{symbol}{amount}"


def render_claim_pdf(data: dict, password: str) -> bytes:
    """
    Build the password-protected mediclaim PDF.

    `data` carries the claim facts (patient, doctor, hospital, clinical
    detail, invoice, verification hash). `password` becomes the PDF's open
    password — the patient's `.mtr` passphrase, so the document can only be
    opened by whoever could open the vault it came from.

    Returns raw PDF bytes.
    """
    appointment_code = data.get("appointment_code") or "—"
    url = verification_url(appointment_code)
    qr_img = build_verification_qr(url)

    encrypt = StandardEncryption(
        userPassword=password,
        ownerPassword=password,
        canPrint=1,
        canModify=0,
        canCopy=0,
        canAnnotate=0,
        strength=128,
    )

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, encrypt=encrypt)
    c.setTitle(f"MedTour Verified Mediclaim — {appointment_code}")
    c.setAuthor("MedTour Navigator")
    c.setSubject("Verified Mediclaim Report")

    styles = getSampleStyleSheet()
    h_section = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=BRAND,
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12.5,
        textColor=INK,
        alignment=TA_LEFT,
    )
    label = ParagraphStyle(
        "Label",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )
    small = ParagraphStyle(
        "Small",
        parent=body,
        fontSize=7.5,
        leading=10,
        textColor=MUTED,
    )
    center_small = ParagraphStyle(
        "CenterSmall",
        parent=small,
        alignment=TA_CENTER,
    )

    y = PAGE_H - MARGIN

    # ------------------------------------------------------------------
    # Letterhead
    # ------------------------------------------------------------------
    c.setFillColor(BRAND)
    c.rect(0, PAGE_H - 30 * mm, PAGE_W, 30 * mm, stroke=0, fill=1)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGIN, PAGE_H - 15 * mm, "MedTour")

    c.setFont("Helvetica", 8.5)
    c.drawString(MARGIN, PAGE_H - 20 * mm, "VERIFIED MEDICLAIM REPORT")

    # "IS VERIFIED" badge — only true once the patient has paid to generate
    # this document, which is the only moment it can exist at all.
    badge_text = "IS VERIFIED"
    c.setFont("Helvetica-Bold", 9)
    bw = stringWidth(badge_text, "Helvetica-Bold", 9) + 12
    bx = PAGE_W - MARGIN - bw
    c.setFillColor(colors.white)
    c.roundRect(bx, PAGE_H - 18.5 * mm, bw, 8 * mm, 3, stroke=0, fill=1)
    c.setFillColor(ALERT)
    c.drawCentredString(bx + bw / 2, PAGE_H - 15.9 * mm, badge_text)

    c.setFillColor(colors.white)
    c.setFont("Helvetica", 7.5)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 23.5 * mm, f"Claim {appointment_code}")

    y = PAGE_H - 38 * mm

    # ------------------------------------------------------------------
    # Page frame + pagination
    #
    # The QR block is pinned to the bottom of the LAST page, so content must
    # never be allowed to run into it. Everything below reserves that strip
    # and rolls onto a fresh sheet when it runs out of room — otherwise a
    # long diagnosis plus notes silently overprints the verification QR.
    # ------------------------------------------------------------------
    QR_RESERVE = 62 * mm  # QR block (26mm) + its captions + breathing room

    def draw_continuation_header():
        nonlocal y
        c.setFillColor(BRAND)
        c.rect(0, PAGE_H - 16 * mm, PAGE_W, 16 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN, PAGE_H - 10.5 * mm, "MedTour")
        c.setFont("Helvetica", 7.5)
        c.drawRightString(
            PAGE_W - MARGIN, PAGE_H - 10.2 * mm, f"Verified Mediclaim — {appointment_code}"
        )
        y = PAGE_H - 24 * mm

    def ensure_space(needed_mm: float):
        """Roll to a new page when the current one cannot hold `needed_mm`."""
        nonlocal y
        if y - needed_mm < MARGIN + QR_RESERVE:
            c.showPage()
            draw_continuation_header()

    def section(title: str, block_mm: float = 24):
        """
        Section header.

        `block_mm` is roughly how tall the content under it is. Reserving it
        here (rather than only the 11mm header) is what stops a header landing
        on the last line of a page with its fields on the next one.
        """
        nonlocal y
        ensure_space(11 * mm + block_mm)
        c.setFillColor(BRAND_LIGHT)
        c.roundRect(MARGIN, y - 5 * mm, CONTENT_W, 6.5 * mm, 2, stroke=0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(MARGIN + 3 * mm, y - 3.2 * mm, title.upper())
        y -= 11 * mm

    def fields(pairs, cols: int = 2):
        nonlocal y
        rows = (len(pairs) + cols - 1) // cols
        ensure_space(rows * 12 * mm + 2 * mm)
        col_w = CONTENT_W / cols
        for i, (k, v) in enumerate(pairs):
            col = i % cols
            row = i // cols
            x = MARGIN + col * col_w
            yy = y - row * 12 * mm
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7)
            c.drawString(x, yy, (k or "").upper())
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 9)
            text = str(v) if v not in (None, "") else "—"
            # wrap the value inside its column
            max_w = col_w - 4 * mm
            words = text.split(" ")
            lines, cur = [], ""
            for w in words:
                trial = (cur + " " + w).strip()
                if stringWidth(trial, "Helvetica-Bold", 9) <= max_w or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            for li, line in enumerate(lines[:3]):
                c.drawString(x, yy - 4.2 * mm - li * 4 * mm, line)
        rows = (len(pairs) + cols - 1) // cols
        y -= rows * 12 * mm + 2 * mm

    def paragraph(text: str, max_chars: int = 120):
        nonlocal y
        from reportlab.platypus import Paragraph
        p = Paragraph((text or "—").replace("\n", "<br/>"), body)
        w, h = p.wrapOn(c, CONTENT_W, 200 * mm)
        ensure_space(h / mm + 3)
        p.drawOn(c, MARGIN, y - h)
        y -= h + 3 * mm

    def labeled_paragraph(field_label: str, text: str):
        """Free-text value under a small caption.

        `fields()` clips every value to three lines so the grid stays tidy —
        fine for a passport number, wrong for allergies or a diagnosis, where
        the clipped remainder is exactly the data the insurer needs. Anything
        open-ended goes through here instead and wraps in full.
        """
        nonlocal y
        from reportlab.platypus import Paragraph
        body_text = (text or "").strip()
        if not body_text:
            return
        p = Paragraph(body_text.replace("\n", "<br/>"), body)
        w, h = p.wrapOn(c, CONTENT_W, 200 * mm)
        ensure_space(4 * mm + h / mm + 4)
        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(MARGIN, y, field_label.upper())
        y -= 4 * mm
        p.drawOn(c, MARGIN, y - h)
        y -= h + 4 * mm

    # ------------------------------------------------------------------
    # Patient — the booking identity, plus whatever the patient's own `.mtr`
    # carried. Insurers ask for passport, policy and allergies specifically,
    # so they are printed when supplied and quietly absent when not.
    # ------------------------------------------------------------------
    patient = data.get("patient") or {}

    section("Patient", 64)
    fields(
        [
            ("Full name", data.get("patient_name") or patient.get("full_name")),
            ("Appointment id", appointment_code),
            ("Department", data.get("department")),
            ("Visit date", _fmt_dt(data.get("appointment_time"))),
            ("Passport no", patient.get("passport_no")),
            ("National ID", patient.get("national_id_no")),
            ("Date of birth", patient.get("date_of_birth")),
            ("Nationality", patient.get("nationality")),
            ("Gender", patient.get("gender")),
            ("Blood type", patient.get("blood_type")),
        ]
    )

    if patient.get("allergies") or patient.get("conditions") or patient.get("medications"):
        section("Patient medical profile", 34)
        labeled_paragraph("Allergies", patient.get("allergies"))
        labeled_paragraph("Chronic conditions", patient.get("conditions"))
        labeled_paragraph("Current medications", patient.get("medications"))

    if patient.get("insurance_provider") or patient.get("insurance_policy_no"):
        section("Insurance", 26)
        fields(
            [
                ("Provider", patient.get("insurance_provider")),
                ("Policy no", patient.get("insurance_policy_no")),
            ]
        )

    if patient.get("emergency_contact_name") or patient.get("emergency_contact_phone"):
        section("Emergency contact", 26)
        fields(
            [
                ("Name", patient.get("emergency_contact_name")),
                ("Phone", patient.get("emergency_contact_phone")),
            ]
        )

    # ------------------------------------------------------------------
    # Doctor who operated
    # ------------------------------------------------------------------
    section("Doctor who operated", 50)
    verified = bool(data.get("doctor_verified"))
    fields(
        [
            ("Name", data.get("doctor_name")),
            ("Reg. number", data.get("doctor_reg_number")),
            ("State council", data.get("doctor_state_council")),
            (
                "NMC verification",
                "VERIFIED — " + _fmt_dt(data.get("doctor_verified_at"))
                if verified
                else "Not verified",
            ),
        ]
    )

    # ------------------------------------------------------------------
    # Hospital
    # ------------------------------------------------------------------
    section("Hospital", 26)
    fields(
        [
            ("Name", data.get("hospital_name")),
            ("Address", data.get("hospital_address")),
        ]
    )

    # ------------------------------------------------------------------
    # Clinical
    # ------------------------------------------------------------------
    section("Reason for the visit", 28)
    paragraph(data.get("reason"))

    section("Diagnosis", 28)
    paragraph(data.get("diagnosis"))

    section("Prescription", 28)
    paragraph(data.get("prescription"))

    if data.get("diagnosis_notes"):
        section("Clinical notes", 28)
        paragraph(data.get("diagnosis_notes"))

    # ------------------------------------------------------------------
    # Invoice — the doctor's stage-2 bill for the visit, laid out as the
    # table the doctor actually filled in, then the one-time report fee the
    # patient paid to produce this document. They are separate amounts and
    # are kept separate: conflating the bill with the $15 generation fee is
    # how a claim gets rejected.
    # ------------------------------------------------------------------
    invoice = data.get("invoice") or {}
    line_items = invoice.get("line_items") or []
    total = data.get("amount")
    currency = (data.get("currency") or invoice.get("currency") or "USD").upper()

    # The whole invoice block is reserved up front so the header, the table
    # and the totals stay together where possible; each row also reserves on
    # its own in case a long description pushes the table past a page.
    y -= 2 * mm
    section("Invoice", min(120.0, 52 + len(line_items) * 8))

    c.setFillColor(MUTED)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(MARGIN, y, f"INVOICE {data.get('invoice_number') or '—'}")
    if invoice.get("issued_on"):
        c.drawRightString(PAGE_W - MARGIN, y, f"Issued {invoice['issued_on']}")
    y -= 5 * mm

    if line_items:
        col_desc = MARGIN
        col_qty = MARGIN + CONTENT_W * 0.52
        col_unit = MARGIN + CONTENT_W * 0.72
        col_amt = PAGE_W - MARGIN

        c.setFillColor(MUTED)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(col_desc, y, "DESCRIPTION")
        c.drawRightString(col_qty, y, "QTY")
        c.drawRightString(col_unit, y, "UNIT PRICE")
        c.drawRightString(col_amt, y, "AMOUNT")
        y -= 3 * mm
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, y, PAGE_W - MARGIN, y)
        y -= 4.5 * mm

        for item in line_items:
            ensure_space(14 * mm)
            qty = float(item.get("quantity") or 0)
            unit = float(item.get("unit_price") or 0)
            amount = qty * unit
            c.setFillColor(INK)
            c.setFont("Helvetica", 8.5)
            # Description gets the wide column and wraps inside it if long.
            from reportlab.platypus import Paragraph as _P

            dp = _P(str(item.get("description") or "—"), body)
            dw, dh = dp.wrapOn(c, CONTENT_W * 0.50, 20 * mm)
            dp.drawOn(c, col_desc, y - dh + 2.5 * mm)
            c.setFont("Helvetica", 8.5)
            c.drawRightString(col_qty, y, f"{qty:g}")
            c.drawRightString(col_unit, y, _money(unit, currency))
            c.drawRightString(col_amt, y, _money(amount, currency))
            y -= max(5.5 * mm, dh + 2 * mm)
            y -= 1.5 * mm

        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN, y + 1.5 * mm, PAGE_W - MARGIN, y + 1.5 * mm)

    def money_row(label: str, value: str, strong: bool = False):
        nonlocal y
        ensure_space(7 * mm)
        c.setFillColor(INK if strong else MUTED)
        c.setFont("Helvetica-Bold" if strong else "Helvetica", 9.5 if strong else 8.5)
        c.drawString(MARGIN + 6 * mm, y, label)
        c.drawRightString(PAGE_W - MARGIN, y, value)
        y -= 5.5 * mm

    y -= 2 * mm
    if invoice.get("subtotal") is not None:
        money_row("Subtotal", _money(invoice["subtotal"], currency))
    if invoice.get("tax_amount"):
        money_row("Tax", _money(invoice["tax_amount"], currency))

    # Total — fall back to "visit charges" wording when the doctor supplied a
    # single figure instead of a table.
    ensure_space(12 * mm)
    c.setFillColor(BRAND)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(MARGIN, y, "TOTAL" if line_items else "VISIT CHARGES")
    c.drawRightString(PAGE_W - MARGIN, y, _money(total, currency))
    y -= 7 * mm

    if invoice.get("notes"):
        labeled_paragraph("Invoice notes", invoice["notes"])

    y -= 1 * mm
    ensure_space(16 * mm)
    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN, y + 3 * mm, PAGE_W - MARGIN, y + 3 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(MARGIN, y, "Verified report generation (one-time)")
    c.drawRightString(
        PAGE_W - MARGIN,
        y,
        _money(data.get("report_fee", 15.0), data.get("report_fee_currency") or "USD"),
    )
    y -= 4.5 * mm
    c.setFont("Helvetica", 7.5)
    c.drawString(
        MARGIN,
        y,
        f"Paid {_fmt_dt(data.get('claim_purchased_at'))} — unlocks this document "
        f"and every future re-download of it.",
    )
    y -= 5 * mm

    c.setStrokeColor(RULE)
    c.setLineWidth(0.5)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 5 * mm

    # ------------------------------------------------------------------
    # Verification hash
    # ------------------------------------------------------------------
    ensure_space(20 * mm)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawString(MARGIN, y, "VERIFICATION HASH")
    y -= 4 * mm
    c.setFillColor(INK)
    c.setFont("Courier", 7)
    vhash = data.get("verification_hash") or "—"
    c.drawString(MARGIN, y, vhash[:52])
    y -= 9 * mm

    # ------------------------------------------------------------------
    # QR + verification link, at the bottom
    # ------------------------------------------------------------------
    qr_size = 26 * mm
    qr_x = MARGIN
    qr_y = MARGIN + 22 * mm
    c.drawImage(
        ImageReader(qr_img),
        qr_x,
        qr_y,
        width=qr_size,
        height=qr_size,
        mask="auto",
    )

    tx = qr_x + qr_size + 6 * mm
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(tx, qr_y + qr_size - 5 * mm, "Scan to check verification status")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawString(
        tx,
        qr_y + qr_size - 10 * mm,
        "Shows the operating doctor's verification, hospital, patient and a verified badge.",
    )

    c.setFillColor(BRAND)
    c.setFont("Helvetica", 7.5)
    c.drawString(tx, qr_y + qr_size - 15.5 * mm, url)

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7)
    c.drawCentredString(
        PAGE_W / 2,
        MARGIN - 5 * mm,
        "This document is password-protected with your MedTour vault (.mtr) passphrase.",
    )
    c.drawCentredString(
        PAGE_W / 2,
        MARGIN - 9 * mm,
        "MedTour Navigator · Verified Mediclaim Report · Keep for insurance submission.",
    )

    c.showPage()
    c.save()
    return buf.getvalue()


def render_claim_pdf_base64(data: dict, password: str) -> str:
    """Same as `render_claim_pdf` but ready to hand straight to the client."""
    return base64.b64encode(render_claim_pdf(data, password)).decode("ascii")
