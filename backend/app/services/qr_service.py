"""
Backend-side QR minting.

Two different QR codes exist in this product and both are produced here, not
in the browser:

  1. The doctor's discharge QR — minted when the doctor saves a diagnosis.
     It carries the appointment code and the clinical detail, and the ONLY
     thing that can read it is the patient's Visits page, which compares the
     embedded appointment id against its own upcoming appointment before it
     will auto-enter anything or mark the visit completed.

  2. The verification QR printed at the bottom of the mediclaim PDF — a
     plain link anyone can scan to check the claim's status.

Clinical detail only ever exists inside payload (1). It is never written to
PostgreSQL; the server builds the QR, the patient scans it, and from that
moment the data lives on the patient's device and in their `.mtr` vault.
"""

import base64
import hashlib
import io
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import qrcode


def build_qr_png_base64(payload: str, box_size: int = 8, border: int = 2) -> str:
    """
    Render a QR for `payload` and return it as a base64 PNG data string.

    Kept as base64 rather than a file so it can be handed straight back in a
    JSON response and dropped into an <img> tag.
    """
    img = qrcode.make(payload, box_size=box_size, border=border)._img
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_diagnosis_payload(
    appointment_code: str,
    appointment_id: int,
    diagnosis: str,
    prescription: str,
    diagnosis_notes: str | None = None,
    invoice: dict | None = None,
) -> str:
    """
    Build the encrypted JSON payload for the doctor's discharge QR.

    The payload is encrypted backend-side with AES-256-GCM using the unique
    appointment code (aID) as the symmetric derivation secret. Anyone scanning
    with an ordinary camera or third-party scanner sees only ciphertext,
    preserving medical privacy.

    Outer Shape:
        {"code":"MT-XXXXXXXX","encrypted":true,"iv":"...","data":"..."}
    """
    inner = {
        "code": appointment_code,
        "id": appointment_id,
        "dx": diagnosis,
        "rx": prescription,
        "app": "medtour",
    }
    if diagnosis_notes:
        inner["notes"] = diagnosis_notes
    if invoice:
        inner["bill"] = invoice

    plain_bytes = json.dumps(inner, ensure_ascii=False).encode("utf-8")

    # Derive 256-bit symmetric key from appointment code
    key = hashlib.sha256(appointment_code.strip().encode("utf-8")).digest()
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plain_bytes, None)

    envelope = {
        "code": appointment_code,
        "id": appointment_id,
        "encrypted": True,
        "iv": base64.b64encode(iv).decode("ascii"),
        "data": base64.b64encode(ciphertext).decode("ascii"),
    }
    return json.dumps(envelope, separators=(",", ":"))
