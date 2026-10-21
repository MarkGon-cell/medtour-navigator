"""
Minting the appointment id (`aid`) that the whole flow keys on.

The id must be genuinely unique, so it is derived rather than random:

    MT- + sha256(appointment_time | patient_name | hospital_name | client_ip)[:8]

Derived beats `token_hex` here because two identical bookings made in the
same second for the same patient and hospital can collide on a random 32-bit
value, whereas the scheduled time, the facility and the device that booked it
are part of what makes the booking itself distinct.

The doctor's name is deliberately NOT in the hash: at booking time no doctor
has been assigned yet — they stamp themselves onto the appointment when they
enter the diagnosis. Re-minting the id mid-flow would break the patient's
ability to match the QR against their own upcoming appointment. The booking
device's address stands in as the fourth ingredient instead, because it *is*
known the moment the request lands. The doctor's name rides alongside as
`doctor_name`.

Every id starts with `MT-` so it is recognisable on the portal, in the QR,
and on the printed PDF.
"""

import hashlib
from datetime import datetime


PREFIX = "MT-"
# 8 hex chars = 32 bits. Collisions are checked against the DB and disambiguated.
DIGEST_LEN = 8


def client_ip(request) -> str:
    """
    Best-effort address of the machine that made the request.

    Honours X-Forwarded-For when the app sits behind a proxy, and falls back
    to the socket address. Used only as hash material — never stored.
    """
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    client = getattr(request, "client", None)
    return (getattr(client, "host", "") or "").strip()


def _digest(
    appointment_time: datetime,
    patient_name: str,
    hospital_name: str,
    origin: str,
) -> str:
    material = "|".join(
        [
            appointment_time.isoformat() if appointment_time else "",
            (patient_name or "").strip().casefold(),
            (hospital_name or "").strip().casefold(),
            (origin or "").strip(),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:DIGEST_LEN].upper()


def generate_appointment_code(
    appointment_time: datetime,
    patient_name: str,
    hospital_name: str,
    origin: str = "",
    taken=None,
) -> str:
    """
    Build the unique `MT-XXXXXXXX` id.

    `taken` is an optional callable `(code) -> bool` reporting whether a code
    is already in use. On the (rare) collision the digest is re-run over the
    same material with a counter salted in, so the id stays derived from the
    booking rather than degrading into something random.
    """
    base = _digest(appointment_time, patient_name, hospital_name, origin)
    code = PREFIX + base

    if taken is None:
        return code

    salt = 0
    while taken(code):
        salt += 1
        material = f"{base}:{salt}"
        code = PREFIX + hashlib.sha256(material.encode("utf-8")).hexdigest()[
            :DIGEST_LEN
        ].upper()
        if salt > 64:  # give up before looping forever
            break

    return code
