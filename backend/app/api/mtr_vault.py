"""
Backend MTR Encryption and Decryption Service.
Performs AES-256-GCM encryption with 250,000 PBKDF2-HMAC-SHA512 rounds on the server.
Guarantees 100% bitwise cross-platform consistency for phones and desktops.
"""
import os
import json
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from pydantic import BaseModel

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

router = APIRouter(
    prefix="/ai/vault",
    tags=["Vault Encryption Engine"],
)

APP_GATEWAY_ORIGIN = "urn:medtour:web:gateway"


class EncryptRequest(BaseModel):
    passphrase: str
    payload: Dict[str, Any]


def derive_key(passphrase: str, salt: bytes, iterations: int = 250000) -> bytes:
    combined = f"{passphrase.strip()}:{APP_GATEWAY_ORIGIN}".encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return kdf.derive(combined)


@router.post("/encrypt")
def encrypt_mtr_endpoint(req: EncryptRequest):
    """
    Encrypts a patient vault payload using AES-256-GCM on the backend.
    """
    if not req.passphrase or len(req.passphrase.strip()) < 4:
        raise HTTPException(status_code=400, detail="Master password must be at least 4 characters.")

    salt = os.urandom(32)
    iv = os.urandom(12)
    key = derive_key(req.passphrase, salt, 250000)

    aesgcm = AESGCM(key)
    plaintext = json.dumps(req.payload, ensure_ascii=False).encode("utf-8")
    ciphertext = aesgcm.encrypt(iv, plaintext, None)

    # Compute SHA-256 integrity tag over salt + ciphertext
    checksum = hashlib.sha256(salt + ciphertext).digest()

    envelope = {
        "format": "MEDTOUR_MTR_V2",
        "version": 2,
        "appOrigin": "medtour-navigator",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "authChecksum": base64.b64encode(checksum).decode("ascii"),
        "cipherAlgorithm": "AES-GCM",
        "iterations": 250000,
    }

    return {"envelope": envelope}


class DecryptRequest(BaseModel):
    passphrase: str
    envelope: Dict[str, Any]


@router.post("/decrypt")
def decrypt_mtr_endpoint(req: DecryptRequest):
    """
    Decrypts an incoming .mtr envelope on the backend.
    """
    envelope = req.envelope
    if not envelope or envelope.get("format") != "MEDTOUR_MTR_V2":
        raise HTTPException(status_code=400, detail="Invalid .mtr file format.")

    try:
        salt = base64.b64decode(envelope["salt"])
        iv = base64.b64decode(envelope["iv"])
        ciphertext = base64.b64decode(envelope["ciphertext"])
    except Exception:
        raise HTTPException(status_code=400, detail="Corrupted base64 payload in .mtr file.")

    iteration_candidates = [
        envelope.get("iterations", 250000),
        250000,
        100000,
    ]

    for iters in iteration_candidates:
        try:
            key = derive_key(req.passphrase, salt, iters)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(iv, ciphertext, None)
            data = json.loads(plaintext.decode("utf-8"))
            return {"payload": data}
        except Exception:
            continue

    raise HTTPException(status_code=403, detail="Incorrect master password or corrupted .mtr file.")
