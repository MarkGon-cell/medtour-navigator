import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from sqlalchemy.orm import Session

from app.models.curated_hospital import CuratedHospital

logger = logging.getLogger(__name__)

NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")


def extract_structured_hospital_data(ai_markdown_text: str, hospital_name: str) -> Dict[str, Any]:
    """
    Given unstructured markdown / text from Google AI Mode search or NIM LLM fallback,
    extract structured fields:
    phone, emergency_phone, website, emergency_available,
    speciality, tier, rating, services, amenities.
    """
    # 1. Regex heuristics first as reliable extraction
    extracted: Dict[str, Any] = {
        "phone": None,
        "emergency_phone": None,
        "website": None,
        "emergency_available": False,
        "speciality": None,
        "tier": None,
        "rating": None,
        "services": None,
        "amenities": None,
    }

    # Extract website
    web_match = re.search(r'(https?://[^\s)\]"\']+)', ai_markdown_text)
    if web_match:
        url = web_match.group(1).rstrip("./,")
        if not any(blocked in url for blocked in ["google.com", "gstatic.com", "policies.google"]):
            extracted["website"] = url

    # Extract phone numbers
    phone_matches = re.findall(r'(?:\+?91[\s-]?)?(?:0?[1-9]\d{1,4}[\s-]?)?\d{6,8}', ai_markdown_text)
    clean_phones = []
    for p in phone_matches:
        digits = re.sub(r'\D', '', p)
        if len(digits) >= 10:
            clean_phones.append(p.strip())
    if clean_phones:
        extracted["phone"] = clean_phones[0]
        if len(clean_phones) > 1:
            extracted["emergency_phone"] = clean_phones[1]

    # Check emergency availability
    lower_text = ai_markdown_text.lower()
    if any(k in lower_text for k in ["24/7", "24 hours", "emergency ward", "emergency department", "trauma center", "casualty"]):
        extracted["emergency_available"] = True

    # Rating regex
    rating_match = re.search(r'([1-5](?:\.\d)?)\s*(?:stars?|/5|\sout of 5)', ai_markdown_text, re.IGNORECASE)
    if rating_match:
        try:
            extracted["rating"] = float(rating_match.group(1))
        except ValueError:
            pass

    # If NVIDIA_NIM_API_KEY is available, we can pass to NIM to parse perfectly structured JSON
    if NVIDIA_NIM_API_KEY:
        try:
            prompt = f"""You are a medical data extraction specialist.
Extract clean hospital details from the text below for hospital: "{hospital_name}".
Text:
\"\"\"
{ai_markdown_text[:3000]}
\"\"\"

Return ONLY a valid JSON object with EXACTLY these keys:
{{
  "phone": "primary phone or null",
  "emergency_phone": "emergency or ambulance helpline or null",
  "website": "official URL or null",
  "emergency_available": true or false,
  "speciality": "comma-separated medical specialties (e.g. Cardiology, Neurology) or null",
  "tier": "hospital tier category, e.g. Tier 1 Tertiary Care / Tier 2 Secondary Care / Multi-Speciality Clinic",
  "rating": numeric rating between 1.0 and 5.0 or null,
  "services": "comma-separated clinical services (e.g. ICU, NICU, Dialysis, Diagnostic Imaging, Surgery)",
  "amenities": "comma-separated amenities (e.g. 24/7 Pharmacy, Cashless Insurance, Cafeteria, Private Rooms, Valet Parking)"
}}
Do NOT output markdown code fences, explanation, or anything else besides the raw JSON object."""

            resp = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {NVIDIA_NIM_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta/llama-3.1-8b-instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 512
                },
                timeout=12
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"].strip()
                # strip possible json fences
                content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
                content = re.sub(r'```$', '', content, flags=re.MULTILINE).strip()
                parsed = json.loads(content)
                for k in extracted.keys():
                    if parsed.get(k) is not None:
                        extracted[k] = parsed[k]
        except Exception as e:
            logger.warning(f"NIM structuring fallback skipped or failed: {e}")

    return extracted


def enrich_curated_hospital_from_ai(
    db: Session,
    hospital: CuratedHospital,
    ai_text: str
) -> CuratedHospital:
    """
    Enriches an existing CuratedHospital row with AI data, filling missing fields:
    phone, emergency_phone, website, emergency_available,
    speciality, tier, rating, services, amenities.
    """
    data = extract_structured_hospital_data(ai_text, hospital.name)

    if not hospital.phone and data.get("phone"):
        hospital.phone = str(data["phone"])
    if not hospital.emergency_phone and data.get("emergency_phone"):
        hospital.emergency_phone = str(data["emergency_phone"])
    if not hospital.website and data.get("website"):
        hospital.website = str(data["website"])
    if data.get("emergency_available") is not None:
        hospital.emergency_available = bool(data["emergency_available"]) or hospital.emergency_available

    if data.get("speciality"):
        hospital.speciality = str(data["speciality"])
    if data.get("tier"):
        hospital.tier = str(data["tier"])
    if data.get("rating") is not None:
        try:
            hospital.rating = float(data["rating"])
        except (ValueError, TypeError):
            pass
    if data.get("services"):
        hospital.services = str(data["services"])
    if data.get("amenities"):
        hospital.amenities = str(data["amenities"])

    hospital.ai_enriched = True
    hospital.ai_enriched_at = datetime.now(timezone.utc)
    hospital.ai_summary = ai_text[:4000]

    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital
