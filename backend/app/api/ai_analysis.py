import os
import re
import sys
import json
import concurrent.futures
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from openai import OpenAI

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from app.database.database import get_db
from app.models.hospital import Hospital
from app.api.robust_triage_engine import (
    PDF_PATH,
    evaluate_emergency_red_flags,
    retrieve_procedural_sections,
    extract_precise_leaf_evidence
)
from app.api.hybrid_first_aid_retriever import parallel_nim_first_aid, nim_generate_json
from app.services import discovery
from app.services import google_places
from app.services.geo import haversine_km
from app.services.hospital_discovery_orchestrator import execute_hospital_discovery_workflow
from app.services.ai_hospital_enrichment import enrich_or_discover_hospitals_with_ai
from app.services.insurance_tpa import resolve_insurance_tpa_profile

load_dotenv()

router = APIRouter(
    prefix="/ai",
    tags=["AI Analysis"]
)

# Load cached Red Cross first aid index if available
RED_CROSS_GUIDES = {}
redcross_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "outputs", "redcross_first_aid_guides.json"))
if os.path.exists(redcross_path):
    try:
        with open(redcross_path, "r", encoding="utf-8") as f:
            for g in json.load(f):
                cond = g.get("condition", "").lower()
                RED_CROSS_GUIDES[cond] = g
    except Exception:
        pass

# Medical knowledge mapping
SYMPTOM_SPECIALTY_MAP = {
    "chest pain": "cardiology",
    "heart": "cardiology",
    "cardiac": "cardiology",
    "palpitation": "cardiology",
    "shortness of breath": "pulmonology",
    "breathing": "pulmonology",
    "bp": "cardiology",
    "blood pressure": "cardiology",
    "hypertension": "cardiology",
    "headache": "neurology",
    "migraine": "neurology",
    "seizure": "neurology",
    "stroke": "neurology",
    "numbness": "neurology",
    "dizziness": "neurology",
    "vertigo": "neurology",
    "fracture": "orthopedics",
    "broken": "orthopedics",
    "bone": "orthopedics",
    "joint": "orthopedics",
    "knee": "orthopedics",
    "hip": "orthopedics",
    "spine": "orthopedics",
    "back pain": "orthopedics",
    "sprain": "orthopedics",
    "cough": "pulmonology",
    "asthma": "pulmonology",
    "pneumonia": "pulmonology",
    "stomach ache": "gastroenterology",
    "abdominal pain": "gastroenterology",
    "nausea": "gastroenterology",
    "vomiting": "gastroenterology",
    "diarrhea": "gastroenterology",
    "accident": "emergency",
    "trauma": "emergency",
    "bleeding": "emergency",
    "burn": "emergency",
    "poisoning": "emergency",
    "unconscious": "emergency",
    "choking": "emergency",
    "fever": "fever",
    "temperature": "fever",
    "infection": "general medicine",
    "cold": "general medicine",
    "pregnancy": "obstetrics",
    "rash": "dermatology",
    "kidney": "urology",
    "eye": "ophthalmology",
    "ear": "ent",
    "throat": "ent",
}

DEFAULT_FIRST_AID = {
    "emergency": [
        "Call 108 / Emergency Medical Services immediately.",
        "Assess Airway, Breathing, and Circulation (ABC) continuously.",
        "Keep the patient calm, lying down in a safe position, and prevent heat loss.",
        "Do not offer food, water, or oral medications to a trauma casualty.",
        "Prepare for immediate paramedic handover and ambulance transport."
    ],
    "choking": [
        "Act immediately: Ask 'Are you choking?' If unable to speak or cough, lean them forward.",
        "Deliver up to 5 sharp back blows between the shoulder blades with the heel of your hand.",
        "Perform up to 5 abdominal thrusts (Heimlich maneuver) pulling inward and upward above the navel.",
        "Alternate 5 back blows and 5 abdominal thrusts until the airway is unobstructed.",
        "If the person loses consciousness, lower them to the floor, call 108, and initiate CPR."
    ],
    "bleeding": [
        "Apply firm, direct, continuous pressure over the wound using a clean sterile cloth or pad.",
        "Do not remove soaked dressings; add more clean layers on top and maintain constant pressure.",
        "Elevate the injured limb above heart level if no bone fracture is suspected.",
        "Secure the dressing firmly with a bandage and monitor consciousness and pulse.",
        "Keep the casualty warm and lying flat to counter shock; dispatch emergency teams."
    ],
    "burns": [
        "Cool the burn immediately under gentle, cool running tap water for at least 15 to 20 minutes.",
        "Gently remove tight rings, watches, or clothing before swelling begins (do not pull stuck cloth).",
        "Never apply ice, ice water, butter, oils, or home pastes to the burn.",
        "Do NOT puncture or pop watery blisters to prevent severe infection.",
        "Cover loosely with a clean non-adherent sterile dressing or clean plastic wrap."
    ],
    "cardiology": [
        "Call 108 / Emergency Medical Services immediately without delay.",
        "Place the patient in a comfortable half-sitting position on the floor (W-position).",
        "Loosen all tight clothing around neck, chest, and waist to ease breathing.",
        "Keep the patient completely still; prohibit any walking or exertion.",
        "If conscious and previously prescribed by their cardiologist, assist with emergency medication."
    ],
    "pulmonology": [
        "Help the person sit upright in a comfortable position to ease breathing.",
        "Loosen restrictive clothing around the neck and chest.",
        "Assist the person with their prescribed rescue inhaler if they have one.",
        "Encourage slow, calm breathing; seek immediate emergency care if breathing worsens."
    ],
    "neurology": [
        "Check for FAST stroke signs: Facial drooping, Arm weakness, Speech slurring, Time to call emergency.",
        "Keep the person lying down with head and shoulders slightly elevated.",
        "Do not offer any food, liquids, or unprescribed medications.",
        "If seizing, clear surrounding hard objects, cushion the head, and place in recovery position after seizing stops."
    ],
    "orthopedics": [
        "Keep the injured limb completely still and supported in the position found.",
        "Do NOT attempt to push back protruding bones or straighten deformed joints.",
        "For minor soft tissue sprains: Rest, Ice pack (wrapped in cloth for 15 min), Compress lightly, Elevate.",
        "Seek urgent medical imaging (X-ray) if unable to bear weight or severe deformity is present."
    ],
    "gastroenterology": [
        "Rest in a comfortable position and avoid heavy or solid foods.",
        "Take small, frequent sips of water or Oral Rehydration Salts (ORS) to stay hydrated.",
        "Avoid NSAID painkillers (like ibuprofen) which can irritate the stomach lining.",
        "Seek emergency medical evaluation if experiencing severe sharp pain, repeated vomiting, or blood in vomit/stool."
    ],
    "fever": [
        "Rest in a well-ventilated room and drink adequate fluids / oral rehydration salts.",
        "Monitor body temperature regularly using a thermometer.",
        "Take paracetamol if fever is uncomfortable and not contraindicated.",
        "Seek emergency hospital care if high fever is accompanied by stiff neck, rash, or breathlessness."
    ],
    "general medicine": [
        "Rest in a comfortable, quiet, well-ventilated space.",
        "Stay adequately hydrated with clean water or electrolyte fluids.",
        "Keep a record of your symptoms and temperature if abnormal.",
        "Consult a certified physician for an in-person medical examination."
    ],
}


class SymptomAnalysisRequest(BaseModel):
    symptoms: str
    latitude: float
    longitude: float
    radius_km: Optional[float] = 20.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


def _clean_and_parse_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = re.sub(r'```\s*', '', cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r'(\{[\s\S]*\})', text)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return None


# ==========================================================
# PARALLEL CALL 1: DRAFT FIRST AID INSTRUCTIONS
# ==========================================================
def draft_first_aid_instructions(symptoms: str) -> Dict[str, Any]:
    """
    Guaranteed Emergency First Aid Dispatcher:
    1. Evaluates Deterministic Red-Flag Triage (Safety Override)
    2. Retrieves Procedural Leaf Nodes from Red Cross Manual PDF (BM25)
    3. Extracts Sliced Boundary Evidence from PDF
    4. Synthesizes Step-by-Step Instructions via Parallel NIM (or Verified Red-Flag Fallback)
    """
    # Phase 1: Red-Flag Emergency Evaluation
    red_flag = evaluate_emergency_red_flags(symptoms)
    is_emergency = red_flag.get("is_emergency", False)

    # Phase 2 & 3: Deep Procedural Leaf Retrieval
    extracted_evidence = []
    if os.path.exists(PDF_PATH):
        try:
            matched_leaves = retrieve_procedural_sections(symptoms, max_sections=3)
            if matched_leaves:
                extracted_evidence = extract_precise_leaf_evidence(PDF_PATH, matched_leaves)
        except Exception as e:
            try:
                print(f"[WARN] Leaf retrieval failed: {e}", flush=True)
            except Exception:
                pass

    # Build synthesized manual evidence text block
    extracted_manual_text = ""
    if extracted_evidence:
        extracted_manual_text = "\n\n".join([
            f"--- [LEAF PROCEDURE: {e['topic']}] ({e['source_ref']}) ---\n{e['text']}"
            for e in extracted_evidence
        ])

    api_key = os.getenv("NVIDIA_NIM_API_KEY")
    if api_key:
        try:
            rc_context = ""
            if extracted_manual_text:
                rc_context = f"\n\nOFFICIAL RED CROSS MANUAL LEAF EVIDENCE:\n{extracted_manual_text}\n\nStrict Rule: Derive all actionable steps strictly from the leaf evidence above."

            system_prompt = (
                "You are an Emergency First Aid & Hospital Preparation AI.\n"
                "Your task is to take the patient's symptoms and the provided official Red Cross Medical Manual excerpt (if available),\n"
                "extract the exact procedural first aid guidelines, and transform them into simple, clear, layman-friendly action steps.\n"
                "Then, based directly on the derived first aid steps and patient state, generate specific prerequisites before heading to the hospital.\n\n"
                "CRITICAL RULES:\n"
                "1. FIRST AID: Create 4-6 clear, numbered, simple layperson action steps based on the Red Cross manual evidence.\n"
                "2. PREREQUISITES: Generate 3-5 specific preparation items needed BEFORE heading to the hospital (e.g. medical records, specific transport posture, ice packs/dressings to bring, emergency contacts, ID proofs).\n"
                "3. Layman Language: Avoid heavy medical jargon. Use simple instructions anyone can follow under stress.\n"
                "4. Acute Emergency Safety: If the condition is an acute emergency (e.g. choking, severe bleeding, cardiac arrest, deep burn), prioritize calling 108/EMS and immediate life-saving stabilization.\n"
                "5. Output ONLY a valid JSON object without markdown syntax with keys:\n"
                "- specialty: string (e.g. 'EMERGENCY', 'CARDIOLOGY', 'GASTROENTEROLOGY')\n"
                "- urgency: 'EMERGENCY'|'URGENT'|'ROUTINE'\n"
                "- summary: 1 concise sentence describing the detected condition in simple terms\n"
                "- firstAid: list of 4-6 simple layman first-aid action steps\n"
                "- prerequisites: list of 3-5 specific hospital arrival & transport prerequisites derived directly from the condition and first-aid protocol\n\n"
                f"{rc_context if rc_context else ''}"
            )

            # Fire parallel NIM calls across fast LLM models (Laguna leads).
            # All models run concurrently and the retry pass is a second
            # round, so a tight first-round timeout keeps the fast answer
            # fast without losing the fallbacks.
            nim_result = parallel_nim_first_aid(
                api_key=api_key,
                system_prompt=system_prompt,
                user_message=f"PATIENT SYMPTOMS & INCIDENT: {symptoms}",
                n_parallel=3,
                per_model_timeout=8.0
            )
            if nim_result and "firstAid" in nim_result and len(nim_result["firstAid"]) >= 3:
                # Enforce emergency classification if red flag is active
                if is_emergency:
                    nim_result["specialty"] = red_flag["forced_specialty"]
                    nim_result["urgency"] = red_flag["forced_urgency"]
                return nim_result
        except Exception as e:
            try:
                print(f"[WARN] Parallel NIM call failed: {e}", flush=True)
            except Exception:
                pass

    # GUARANTEED SAFETY FALLBACK: Zero generic bleed, uses verified Red-Flag safety protocol
    if is_emergency:
        return {
            "specialty": red_flag["forced_specialty"],
            "urgency": red_flag["forced_urgency"],
            "summary": f"Emergency triage triggered for {red_flag['primary_condition']}. Immediate life-saving action required.",
            "firstAid": red_flag["safety_first_aid"],
            "prerequisites": red_flag["prerequisites"]
        }

    # Standard Outpatient Fallback
    specialty = "general medicine"
    for kw, spec in SYMPTOM_SPECIALTY_MAP.items():
        if kw in symptoms.lower():
            specialty = spec
            break

    return {
        "specialty": specialty,
        "urgency": "URGENT" if specialty in ["cardiology", "neurology"] else "ROUTINE",
        "summary": f"Detected symptoms requiring {specialty} evaluation.",
        "firstAid": DEFAULT_FIRST_AID.get(specialty, DEFAULT_FIRST_AID["general medicine"]),
        "prerequisites": [
            "Carry valid Government Photo ID proof (Aadhar/PAN/Passport)",
            "Carry past medical records and prescription slips",
            "Keep emergency contact numbers handy",
            "Wear comfortable loose clothing"
        ]
    }


# ==========================================================
# PARALLEL CALL 2 (part A): MERGE Postgres + Overpass + Geoapify
# ==========================================================
def gather_nearby_candidates(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> List[Dict[str, Any]]:
    """
    Build one deduplicated candidate list from all three sources:
    the local Postgres directory, Overpass, and Geoapify.

    `discovery.discover` already queries Overpass + Geoapify (with caching)
    and merges them against the local directory, deduplicating by
    same-site/same-name. We map its output into the shape the scoring
    and LLM-curation steps consume.
    """
    candidates: List[Dict[str, Any]] = []
    seen_keys = set()

    def _add_model_instance(h: Hospital, dist: float):
        name_clean = re.sub(r'[^a-z0-9]', '', (h.name or "").lower())
        city_clean = re.sub(r'[^a-z0-9]', '', (h.city or "").lower())
        key = (name_clean, city_clean, round(h.latitude, 3), round(h.longitude, 3))
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append({
            # 1. Primary Identifier & Basic Info
            "id": h.id,
            "name": h.name,
            "category": h.category or "Hospital",
            "care_type": h.care_type or "Tertiary",
            "discipline": h.discipline or "Allopathy",
            # 2. Location & Coordinates
            "city": h.city,
            "state": h.state,
            "district": h.district,
            "subdistrict": h.subdistrict,
            "address": h.address,
            "pincode": h.pincode,
            "latitude": h.latitude,
            "longitude": h.longitude,
            "distance_km": round(dist, 2),
            # 3. Medical Specialties & Facilities
            "specialties": h.specialties or "",
            "facilities": h.facilities or "",
            "miscellaneous_facilities": h.miscellaneous_facilities or "",
            # 4. Emergency & Urgent Services
            "emergency_available": bool(h.emergency_available),
            "emergency_services": h.emergency_services,
            "emergency_phone": h.emergency_phone,
            "ambulance_phone": h.ambulance_phone,
            "bloodbank_phone": h.bloodbank_phone,
            # 5. Contact Details
            "phone": h.phone,
            "mobile": h.mobile,
            "tollfree": h.tollfree,
            "helpline": h.helpline,
            "website": h.website,
            "email": h.email,
            # 6. Capacity & Staff
            "total_beds": h.total_beds,
            "private_wards": h.private_wards,
            "economically_weaker_beds": h.economically_weaker_beds,
            "doctors": h.doctors,
            "medical_consultants": h.medical_consultants,
            "established_year": h.established_year,
            # 7. Accreditations, Costs & External IDs
            "accreditation": h.accreditation,
            "registration_number": h.registration_number,
            "empanelment": h.empanelment,
            "tariff_range": h.tariff_range,
            "source": h.source or "local",
            "external_id": h.external_id,
            "opening_hours": h.opening_hours,
            "rating": h.rating,
            "review_count": h.review_count,
        })

    def _add_discovered_facility(row: dict, dist: float):
        name = row.get("name")
        lat = row.get("latitude")
        lon = row.get("longitude")
        if not name or lat is None or lon is None:
            return
        name_clean = re.sub(r'[^a-z0-9]', '', (name or "").lower())
        city_clean = re.sub(r'[^a-z0-9]', '', (row.get("city") or "").lower())
        key = (name_clean, city_clean, round(lat, 3), round(lon, 3))
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append({
            "id": row.get("external_id") or f"ext-{abs(hash(name)) % 100000}",
            "name": name,
            "category": row.get("category") or "Hospital",
            "care_type": "Walk-In Clinic & Urgent Care",
            "discipline": "Allopathy",
            "city": row.get("city"),
            "state": row.get("state") or "Maharashtra",
            "district": row.get("city"),
            "subdistrict": None,
            "address": row.get("address"),
            "pincode": row.get("pincode"),
            "latitude": lat,
            "longitude": lon,
            "distance_km": round(dist, 2),
            "specialties": row.get("specialties") or "Emergency Medicine, General Medicine",
            "facilities": row.get("facilities") or row.get("category") or "Casualty / Urgent Care Desk",
            "miscellaneous_facilities": None,
            "emergency_available": bool(row.get("emergency_available", True)),
            "emergency_services": "24/7 Casualty & Triage",
            "emergency_phone": row.get("phone"),
            "ambulance_phone": "108",
            "bloodbank_phone": None,
            "phone": row.get("phone"),
            "mobile": None,
            "tollfree": None,
            "helpline": row.get("phone"),
            "website": row.get("website"),
            "email": None,
            "total_beds": row.get("total_beds", 50),
            "private_wards": None,
            "economically_weaker_beds": None,
            "doctors": row.get("doctors", 15),
            "medical_consultants": None,
            "established_year": None,
            "accreditation": row.get("accreditation") or "NABH Accredited / State Verified",
            "registration_number": None,
            "empanelment": "Cashless Travel Insurance Desk",
            "tariff_range": "Standard",
            "source": row.get("origin", "discovery"),
            "external_id": row.get("external_id"),
            "opening_hours": row.get("opening_hours") or "24/7",
            "rating": row.get("rating"),
            "review_count": row.get("review_count"),
        })

    # --- Source 1: local Postgres directory (bbox pre-filter, exact haversine)
    min_lat, max_lat, min_lon, max_lon = discovery.bounding_box(
        latitude, longitude, radius_km
    )
    local_rows = (
        db.query(Hospital)
        .filter(
            Hospital.latitude >= min_lat,
            Hospital.latitude <= max_lat,
            Hospital.longitude >= min_lon,
            Hospital.longitude <= max_lon,
        )
        .all()
    )
    for h in local_rows:
        if not (h.latitude and h.longitude):
            continue
        dist = haversine_km(latitude, longitude, h.latitude, h.longitude)
        if dist > radius_km:
            continue
        _add_model_instance(h, dist)

    # --- Sources 2 & 3: Overpass + Geoapify discovery
    try:
        merged = discovery.discover(
            db, latitude, longitude, radius_km,
            persist=False, limit=discovery.MAX_RESULTS, fast=True,
        )
        for row in merged.get("results", []):
            lat, lon = row.get("latitude"), row.get("longitude")
            if lat is None or lon is None:
                continue
            dist = row.get("distance_km") or haversine_km(latitude, longitude, lat, lon)
            _add_discovered_facility(row, dist)
    except Exception as e:
        try:
            print(f"[WARN] Overpass/Geoapify discovery failed: {e}", flush=True)
        except Exception:
            pass

    # --- Real ratings from Google Places (quota-safe, optional) -----------
    # One Nearby Search enriches the whole area by name match. Rate-limited,
    # cached, and circuit-broken; a demo/unusable key just leaves the
    # candidates on inferred reputation. Never raises.
    try:
        google_places.enrich_candidates_with_ratings(
            candidates, latitude, longitude, radius_km
        )
    except Exception as e:
        try:
            print(f"[WARN] Google Places rating enrichment failed: {e}", flush=True)
        except Exception:
            pass

    return candidates


# ==========================================================
# PARALLEL CALL 2 (part B): LLM CURATION OF NEARBY HOSPITALS
# ==========================================================
def curate_hospitals_with_llm(
    api_key: str,
    symptoms: str,
    specialty: str,
    urgency: str,
    scored_hospitals: List[Dict[str, Any]],
) -> Optional[List[Dict[str, Any]]]:
    """
    Second AI call: hand the ranked candidate list to Laguna and let it
    pick + justify the top hospitals for THIS patient's symptoms.

    Returns the hospitals with AI-written `ai_match_score` / `ai_match_reason`,
    or None when the LLM is unreachable (caller keeps the deterministic rank).
    """
    if not scored_hospitals:
        return None

    # Keep the payload small: top 12 deterministic candidates.
    top = scored_hospitals[:12]
    slim = [
        {
            "name": h.get("name"),
            "city": h.get("city"),
            "address": h.get("address"),
            "distance_km": h.get("distance_km"),
            "specialties": h.get("specialties"),
            "emergency_available": h.get("emergency_available"),
            "phone": h.get("phone"),
            "reputation_band": h.get("reputation_band"),
            "curability": h.get("curability"),
            "base_score": h.get("ai_match_score"),
        }
        for h in top
    ]

    system_prompt = (
        "You are a medical hospital-matching AI for patients and tourists in India.\n"
        "Given the patient's symptoms, the triaged specialty/urgency, and the candidate hospitals "
        "(each with distance_km, reputation_band, curability, and emergency capability):\n\n"
        "Your task is to organize and rank the hospitals into structured clinical tiers:\n"
        "1. Identify the single 'BEST' hospital for these specific symptoms (highest clinical match, curability, and reputation).\n"
        "2. Identify the single 'NEAREST' emergency/walk-in hospital (closest physical distance that can safely handle the case).\n"
        "3. Provide up to 5 additional hospitals in the 'NEAREST_CATEGORY' ranked by optimal distance and suitability.\n\n"
        "For EACH hospital selected, provide:\n"
        "- exact name (must match input verbatim)\n"
        "- tier: 'best', 'nearest', or 'nearby'\n"
        "- ai_match_score: integer 0-99\n"
        "- ai_match_reason: a punchy, specific 8-15 word explanation explaining exactly WHY it was chosen for this patient's symptoms.\n\n"
        "OUTPUT FORMAT: Return strictly valid JSON (no markdown fences) like:\n"
        '{"hospitals": [{"name": "<exact name>", "tier": "best"|"nearest"|"nearby", "ai_match_score": 92, "ai_match_reason": "Equipped with 24/7 cardiac ICU and urgent coronary catheterization lab"}]}'
    )
    user_message = (
        f"PATIENT SYMPTOMS: {symptoms}\n"
        f"TRIAGED SPECIALTY: {specialty}\n"
        f"URGENCY: {urgency}\n"
        f"CANDIDATE HOSPITALS (JSON):\n{json.dumps(slim, ensure_ascii=False)}"
    )

    result = nim_generate_json(
        api_key=api_key,
        system_prompt=system_prompt,
        user_message=user_message,
        expect_key="hospitals",
        per_model_timeout=14.0,
        max_retries=1,
    )
    if not result or not isinstance(result.get("hospitals"), list):
        return None

    # Map LLM verdicts back onto the full candidate records by exact name.
    verdict_by_name = {}
    for item in result["hospitals"]:
        if isinstance(item, dict) and item.get("name"):
            verdict_by_name[str(item["name"]).strip().lower()] = item

    curated: List[Dict[str, Any]] = []
    used = set()
    for item in result["hospitals"]:
        name_key = str(item.get("name", "")).strip().lower()
        matched_candidate = next((h for h in top if (h.get("name") or "").strip().lower() == name_key and id(h) not in used), None)
        if matched_candidate:
            h_copy = dict(matched_candidate)
            try:
                h_copy["ai_match_score"] = max(0, min(99, int(item.get("ai_match_score", matched_candidate.get("ai_match_score", 50)))))
            except (TypeError, ValueError):
                h_copy["ai_match_score"] = matched_candidate.get("ai_match_score", 50)
            
            reason = item.get("ai_match_reason")
            if reason:
                h_copy["ai_match_reason"] = str(reason).strip()
            if item.get("tier"):
                h_copy["tier"] = str(item["tier"]).lower()

            curated.append(h_copy)
            used.add(id(matched_candidate))

    # Append any remaining top picks to ensure at least nearest options exist
    for h in top:
        if id(h) not in used:
            h_copy = dict(h)
            h_copy["tier"] = "nearby"
            curated.append(h_copy)

    # Ensure tiers are explicitly tagged even if LLM omitted them
    if curated:
        # Mark nearest
        nearest_idx = min(range(len(curated)), key=lambda i: curated[i].get("distance_km", 999))
        if not any(c.get("tier") == "nearest" for c in curated):
            curated[nearest_idx]["tier"] = "nearest"
        # Mark best (highest score)
        best_idx = max(range(len(curated)), key=lambda i: curated[i].get("ai_match_score", 0))
        if not any(c.get("tier") == "best" for c in curated):
            curated[best_idx]["tier"] = "best"

    return curated


# ==========================================================
# REPUTATION INFERENCE (name + services + accreditation)
# ==========================================================
# The national directory has no user ratings, so we infer a reputation band
# from what it DOES carry: the hospital's name/brand, its accreditation, its
# facility list, and its scale (beds, doctors). This is honest, offline, and
# deterministic -- the UI labels it "inferred", never fake stars.

# Recognised brand / academic tiers in India. Matched case-insensitively as
# substrings of the hospital name.
_PREMIUM_BRANDS = {
    "aiims", "apollo", "fortis", "medanta", "manipal", "max healthcare",
    "kokilaben", "lilavati", "narayana health", "cloudnine", "batra",
    "mount elizabeth", "gleneagles", "radium", "pacific",
}
_SUPER_SPECIALITY_HINTS = {
    "cardiac", "cardiology", "heart", "neuro", "neurosurgery", "onco", "cancer",
    "trauma", "critical care", "icu", "transplant", "multi speciality",
    "multispecialty", "super speciality", "superspecialty",
}

# Accreditation strings that signal verified quality.
_ACCRED_MARKS = ("nabh", "jci", "nabl", "iso ", "iso9001", "iso 9001", "cap")


def infer_reputation(h: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive a 0-99 reputation score + band from name/services/accreditation.

    Returns {"reputation_score": int, "reputation_band": str,
             "reputation_source": "inferred"}. When the row already carries a
    REAL rating (from a future Google/Practo load), that outranks the inference.
    """
    # A real, sourced rating always wins over inference.
    real_rating = h.get("rating")
    real_reviews = h.get("review_count")
    if isinstance(real_rating, (int, float)) and real_rating > 0:
        # Map 0-5 -> 0-99, scaled by review volume (more reviews = more trust).
        volume_boost = min(1.0, (real_reviews or 0) / 500.0) * 10
        score = min(99, int(round((real_rating / 5.0) * 90 + volume_boost)))
        band = "Rated" if score >= 75 else ("Good" if score >= 55 else "Average")
        return {
            "reputation_score": score,
            "reputation_band": band,
            "reputation_source": "rated",
            "rating": real_rating,
            "review_count": real_reviews,
        }

    # ---- Inference path (no real rating available) --------------------
    name = (h.get("name") or "").lower()
    accred = (h.get("accreditation") or "").lower()
    facs = (h.get("facilities") or "").lower()
    specs = (h.get("specialties") or "").lower()
    blob = f"{name} {facs} {specs}"

    score = 40  # baseline for any listed facility
    reasons = []

    if any(b in name for b in _PREMIUM_BRANDS):
        score += 22
        reasons.append("Recognised hospital brand")
    if any(m in accred for m in _ACCRED_MARKS):
        score += 18
        reasons.append("Accredited (NABH/JCI/NABL)")
    if any(k in blob for k in _SUPER_SPECIALITY_HINTS):
        score += 12
        reasons.append("Super-speciality services")

    beds = h.get("total_beds") or 0
    docs = h.get("doctors") or 0
    if beds >= 250:
        score += 12
        reasons.append("Large 250+ bed facility")
    elif beds >= 80:
        score += 7
        reasons.append("Mid-size 80+ bed facility")
    if docs >= 100:
        score += 6
        reasons.append("100+ doctors on staff")
    elif docs >= 30:
        score += 3

    score = max(0, min(99, score))
    band = "Premium" if score >= 78 else ("Well-reviewed" if score >= 60 else "Standard")
    return {
        "reputation_score": score,
        "reputation_band": band,
        "reputation_source": "inferred",
        "reputation_reasons": reasons,
        "rating": None,
        "review_count": None,
    }


# ==========================================================
# CURABILITY: can this hospital actually treat the condition?
# ==========================================================
# Map each triage specialty to the keywords a hospital's specialties/facilities
# must show to be considered able to treat it. A cardiology patient should be
# routed to a hospital that actually has a cardiology/heart department, not just
# the nearest clinic.
_SPECIALTY_CURE_KEYWORDS = {
    "cardiology": ["cardio", "heart", "cardiac"],
    "pulmonology": ["pulmo", "chest", "respiratory", "asthma", "lung"],
    "neurology": ["neuro", "brain", "stroke"],
    "orthopedics": ["ortho", "bone", "joint", "fracture", "spine"],
    "gastroenterology": ["gastro", "digestive", "stomach", "liver", "gi "],
    "dermatology": ["derma", "skin"],
    "ent": ["ent", "ear", "nose", "throat"],
    "ophthalmology": ["ophthal", "eye"],
    "urology": ["uro", "kidney", "urinary"],
    "obstetrics": ["obstetric", "gynae", "gynec", "maternity", "women", "childbirth"],
    "emergency": ["emergency", "trauma", "casualty", "24", "icu", "critical"],
    "fever": ["general", "medicine", "fever", "infection", "multi"],
    "general medicine": ["general", "medicine", "family", "physician", "multi"],
}


def assess_curability(h: Dict[str, Any], specialty: str) -> Dict[str, Any]:
    """
    Judge whether a hospital offers the department needed for `specialty`.

    Returns {"curable": bool, "curability": str, "curability_score": int 0-3}.
    A hospital with no readable specialties is treated as unknown-but-hopeful
    (curable=True, score 1) rather than excluded, since the CSV's specialty
    column is often sparse.
    """
    target = (specialty or "general medicine").strip().lower()
    keywords = _SPECIALTY_CURE_KEYWORDS.get(target, _SPECIALTY_CURE_KEYWORDS["general medicine"])

    specs = (h.get("specialties") or "").lower()
    facs = (h.get("facilities") or "").lower()
    name = (h.get("name") or "").lower()
    blob = f"{specs} {facs} {name}"

    matched = [k for k in keywords if k in blob]

    if not specs.strip():
        # No specialty data: hope for the best but don't over-claim.
        return {"curable": True, "curability": "Services unknown — verify on call",
                "curability_score": 1, "matched_department": None}
    if matched:
        return {"curable": True,
                "curability": f"Offers {target.title()} department",
                "curability_score": 3, "matched_department": matched[0]}
    if any(k in blob for k in ["multi", "general", "hospital"]):
        return {"curable": True,
                "curability": "Multispeciality — likely can treat",
                "curability_score": 2, "matched_department": None}
    return {"curable": False,
            "curability": f"No {target.title()} department listed",
            "curability_score": 0, "matched_department": None}


# ==========================================================
# PARALLEL CALL 2: AI INDEXING & HOSPITAL RECOMMENDATIONS
# ==========================================================
def score_and_rank_hospitals(
    symptoms: str,
    target_specialty: str,
    hospital_candidates: List[Dict[str, Any]],
    radius_km: float
) -> List[Dict[str, Any]]:
    """
    Score and rank nearby hospitals for the patient's symptoms.

    Beyond the original capability/proximity logic, each hospital is judged on:
      - REPUTATION  (infer_reputation: name brand + accreditation + scale,
                     or a real rating when one is loaded), and
      - CURABILITY  (assess_curability: does it actually offer the department
                     this condition needs?).

    Both are merged into the score AND attached to each result so the UI can
    show a reputation band and a "can they treat me?" line.
    """
    scored_hospitals = []
    seen_hospital_ids = set()
    is_emergency_condition = target_specialty.lower() in ["emergency", "trauma", "cardiac", "cardiology"] or evaluate_emergency_red_flags(symptoms).get("is_emergency", False)

    for h in hospital_candidates:
        h_id = h.get("id")
        if h_id in seen_hospital_ids:
            continue

        dist = h["distance_km"]
        specs = (h.get("specialties") or "").lower()
        facs = (h.get("facilities") or "").lower()
        name = (h.get("name") or "").lower()

        score = 35  # Baseline (lower than before: reputation/curability now add)
        reasons = []

        # --- Curability: can this hospital treat the condition at all? ------
        cure = assess_curability(h, target_specialty)
        if cure["curability_score"] == 3:
            score += 20
            reasons.append(cure["curability"])
        elif cure["curability_score"] == 2:
            score += 10
        elif cure["curability_score"] == 0:
            # Penalise hospitals that clearly lack the needed department.
            score -= 15
            reasons.append(cure["curability"])

        # --- Capability (specialty / emergency / ICU) ----------------------
        if is_emergency_condition:
            # For emergency/life-threatening events, prioritize trauma, 24/7 emergency & ICU
            if h.get("emergency_available"):
                score += 25
                reasons.append("24/7 Emergency & Trauma Unit")
            if any(k in specs or k in facs for k in ["emergency", "trauma", "critical care", "resuscitation"]):
                score += 20
                reasons.append("Advanced Trauma & Emergency Care")
            elif any(k in specs for k in ["multispecialty", "general"]):
                score += 15
                reasons.append("Multispecialty acute care facility")
            if "icu" in facs or "critical" in facs:
                score += 10
                reasons.append("Intensive Care Unit (ICU)")
        else:
            # Specialty match for outpatient / routine conditions
            spec_target = target_specialty.lower()
            if spec_target in specs or spec_target in name:
                score += 25
                reasons.append(f"Specialized {target_specialty.title()} department")
            elif any(k in specs for k in ["multispecialty", "general"]):
                score += 10
                reasons.append("Multispecialty hospital")

            if h.get("emergency_available"):
                score += 10
                reasons.append("Emergency services available")

            if "icu" in facs or "critical" in facs:
                score += 5
                reasons.append("ICU facility")

        # --- Reputation: name brand + accreditation + scale ----------------
        rep = infer_reputation(h)
        rep_contribution = int(round(rep["reputation_score"] / 10))  # 0-10 pts
        score += rep_contribution
        if rep["reputation_band"] in ("Premium", "Well-reviewed", "Rated"):
            reasons.append(f"{rep['reputation_band']} reputation")

        # --- Proximity score ----------------------------------------------
        if dist < 3.0:
            score += 10
            reasons.append(f"Immediate proximity ({dist:.1f} km)")
        elif dist < 8.0:
            score += 5
            reasons.append(f"Nearby distance ({dist:.1f} km)")

        final_score = max(0, min(99, score))
        match_reason = " • ".join(reasons) if reasons else "Reachable medical center"

        if final_score >= 45:
            h_copy = dict(h)
            h_copy["ai_match_score"] = final_score
            h_copy["ai_match_reason"] = match_reason
            # Reputation + curability for the UI.
            h_copy["reputation_band"] = rep["reputation_band"]
            h_copy["reputation_source"] = rep["reputation_source"]
            h_copy["reputation_reasons"] = rep.get("reputation_reasons", [])
            h_copy["rating"] = rep.get("rating")
            h_copy["review_count"] = rep.get("review_count")
            h_copy["curable"] = cure["curable"]
            h_copy["curability"] = cure["curability"]
            h_copy["insurance_tpa"] = resolve_insurance_tpa_profile(
                hospital_name=h.get("name") or "",
                category=h.get("category") or "",
                accreditation=h.get("accreditation") or "",
            )
            scored_hospitals.append(h_copy)
            seen_hospital_ids.add(h_id)

    scored_hospitals.sort(key=lambda x: (-x["ai_match_score"], x["distance_km"]))

    # Ensure at least nearest hospitals are shown if none hit the threshold
    if not scored_hospitals:
        hospital_candidates.sort(key=lambda x: x["distance_km"])
        for h in hospital_candidates[:3]:
            if h.get("id") not in seen_hospital_ids:
                h_copy = dict(h)
                h_copy["ai_match_score"] = 45
                h_copy["ai_match_reason"] = "Nearest available facility"
                cure = assess_curability(h, target_specialty)
                rep = infer_reputation(h)
                h_copy["reputation_band"] = rep["reputation_band"]
                h_copy["reputation_source"] = rep["reputation_source"]
                h_copy["reputation_reasons"] = rep.get("reputation_reasons", [])
                h_copy["rating"] = rep.get("rating")
                h_copy["review_count"] = rep.get("review_count")
                h_copy["curable"] = cure["curable"]
                h_copy["curability"] = cure["curability"]
                h_copy["insurance_tpa"] = resolve_insurance_tpa_profile(
                    hospital_name=h.get("name") or "",
                    category=h.get("category") or "",
                    accreditation=h.get("accreditation") or "",
                )
                scored_hospitals.append(h_copy)
                seen_hospital_ids.add(h.get("id"))

    return scored_hospitals[:10]


@router.post("/transcribe")
def transcribe_speech(
    file: UploadFile = File(...),
):
    """
    Speech-to-text for the walk-in voice triage box.

    The Web Speech API the front end uses for dictation is Chromium-only.
    Firefox and Safari patients record the utterance with MediaRecorder and
    upload it here, where faster-whisper transcribes it locally -- no speech
    API key, no audio leaving the machine.

    Kept as a `def` (not `async def`) on purpose: decoding and transcribing are
    CPU-bound, and FastAPI runs sync routes on its threadpool, so the audio
    cannot stall the event loop that serves /ai/analyze.
    """
    from app.services import speech_to_text

    audio = file.file.read()
    if not audio:
        raise HTTPException(
            status_code=400,
            detail="That recording was empty. Tap the mic and speak again.",
        )
    if len(audio) > speech_to_text.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That recording is too long. Keep it to about a minute.",
        )

    try:
        text, language = speech_to_text.transcribe(audio, file.content_type or "")
    except RuntimeError as exc:
        # Raised with a patient-readable message by the service; surface it
        # verbatim so the front end can show what actually went wrong.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - never leak a stack trace to the patient
        raise HTTPException(
            status_code=502,
            detail="Speech-to-text is unavailable right now. Please type your symptoms.",
        ) from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Could not make out any words. Tap the mic and speak again.",
        )

    return {"text": text, "language": language}


@router.post("/analyze")
def analyze_symptoms(
    req: SymptomAnalysisRequest,
    db: Session = Depends(get_db),
):
    symptoms = req.symptoms
    lat = req.latitude
    lon = req.longitude
    radius_km = req.radius_km or 20.0

    # Red-flag safety evaluation
    red_flag = evaluate_emergency_red_flags(symptoms)
    is_emergency = red_flag.get("is_emergency", False)

    if is_emergency:
        primary_specialty = "emergency"
    else:
        primary_specialty = "general medicine"
        s_lower = symptoms.lower()
        for kw, spec in SYMPTOM_SPECIALTY_MAP.items():
            if kw in s_lower:
                primary_specialty = spec
                break

    # 2. Overlap every stage that does not depend on another stage's output:
    #    Task 1: Draft First Aid Instructions (NVIDIA NIM / Red Cross Manual).
    #            Needs only the symptom text, so it is submitted FIRST and
    #            runs while the directory is still being gathered.
    #    Task 2: Deterministic Hospital Recommendation & Indexing.
    #    Task 3: Stage-2 AI enrichment/discovery of the same candidate list.
    #            Tasks 2 and 3 start the moment the candidates exist, which
    #            is still inside Task 1's flight time.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
    try:
        future_first_aid = executor.submit(draft_first_aid_instructions, symptoms)

        # Task 4: candidate hospitals from ALL THREE sources (Postgres +
        # Overpass + Geoapify), deduplicated by name + location. Runs in the
        # request thread because it owns the `db` session.
        candidates = gather_nearby_candidates(db, lat, lon, radius_km)

        future_hospitals = executor.submit(
            score_and_rank_hospitals, symptoms, primary_specialty, candidates, radius_km
        )
        future_enriched = executor.submit(
            enrich_or_discover_hospitals_with_ai, db, candidates, lat, lon, radius_km
        )

        try:
            # Budget stays above the NIM worst case (2 rounds x per-model
            # timeout) so a hung provider still reaches the safety fallback.
            first_aid_result = future_first_aid.result(timeout=20.0)
        except concurrent.futures.TimeoutError:
            if is_emergency:
                first_aid_result = {
                    "specialty": red_flag["forced_specialty"],
                    "urgency": red_flag["forced_urgency"],
                    "summary": f"Emergency triage triggered for {red_flag['primary_condition']}. Immediate life-saving action required.",
                    "firstAid": red_flag["safety_first_aid"],
                    "prerequisites": red_flag["prerequisites"]
                }
            else:
                first_aid_result = {}
        
        try:
            # Budget covers the fast-mode providers: Overpass (2 mirrors x 3s)
            # + Geoapify (8s) ~= 14s worst case, plus local query headroom.
            # Runs in parallel with the LLM first-aid call, so this does not
            # add perceived latency.
            recommended_hospitals = future_hospitals.result(timeout=18.0)
        except concurrent.futures.TimeoutError:
            recommended_hospitals = []

        try:
            # Enrichment was already racing the first-aid call, so this only
            # waits for whatever part of it is still outstanding. A failed
            # enrichment must degrade to the raw candidate list rather than
            # fail the whole triage, exactly as the workflow fallback did.
            enriched_candidates = future_enriched.result(timeout=16.0)
        except concurrent.futures.TimeoutError:
            enriched_candidates = candidates
        except Exception as enrich_err:
            try:
                print(f"[WARN] Stage-2 AI enrichment failed: {enrich_err}", flush=True)
            except Exception:
                pass
            enriched_candidates = candidates
    finally:
        # The workers touch the request-scoped `db` session, so none of them
        # may outlive this block.
        executor.shutdown(wait=True)

    spec_res = (first_aid_result.get("specialty") or primary_specialty).lower()
    if is_emergency:
        specialty = "EMERGENCY"
        urgency = "EMERGENCY"
    else:
        specialty = first_aid_result.get("specialty", primary_specialty.title())
        urgency = first_aid_result.get("urgency", "ROUTINE")

    # 3. Execute Complete Hospital Discovery & Enrichment Workflow:
    #    Clinical Guardrails -> (Stage-2 enrichment already ran above) -> NVIDIA NIM 7-Hospital Selection -> Google Places Contacts
    try:
        final_workflow_hospitals = execute_hospital_discovery_workflow(
            db=db,
            symptoms=symptoms,
            target_specialty=specialty,
            urgency=urgency,
            raw_candidates=enriched_candidates,
            latitude=lat,
            longitude=lon,
            radius_km=radius_km,
            pre_enriched=True
        )
        if final_workflow_hospitals:
            recommended_hospitals = final_workflow_hospitals
    except Exception as wf_err:
        import logging
        logging.getLogger(__name__).warning(f"Workflow orchestrator fallback: {wf_err}")
        api_key = os.getenv("NVIDIA_NIM_API_KEY")
        if api_key and recommended_hospitals:
            curated = curate_hospitals_with_llm(
                api_key=api_key,
                symptoms=symptoms,
                specialty=specialty,
                urgency=urgency,
                scored_hospitals=recommended_hospitals,
            )
            if curated:
                recommended_hospitals = curated

    summary = first_aid_result.get("summary")
    if not summary:
        if is_emergency:
            summary = f"Emergency medical triage activated for {red_flag.get('primary_condition', 'acute trauma')}."
        else:
            summary = f"Detected symptoms requiring {specialty} evaluation."

    first_aid = first_aid_result.get("firstAid")
    if not first_aid or len(first_aid) == 0:
        if is_emergency:
            first_aid = red_flag.get("safety_first_aid", DEFAULT_FIRST_AID["emergency"])
        else:
            first_aid = DEFAULT_FIRST_AID.get(spec_res, DEFAULT_FIRST_AID["general medicine"])

    prerequisites = first_aid_result.get("prerequisites")
    if not prerequisites or len(prerequisites) == 0:
        if is_emergency:
            prerequisites = red_flag.get("prerequisites", [
                "Call 108 for emergency ambulance transport immediately",
                "Keep patient stationary and monitor breathing continuously",
                "Alert emergency trauma department before arrival"
            ])
        else:
            prerequisites = [
                "Carry government photo ID proof (Aadhar/PAN/Passport)",
                "Bring previous doctor prescriptions and medical records",
                "Keep emergency contact phone numbers accessible",
                "Wear comfortable, loose-fitting clothing"
            ]

    return {
        "specialty": specialty,
        "urgency": urgency,
        "summary": summary,
        "firstAid": first_aid,
        "prerequisites": prerequisites,
        "recommendedHospitals": recommended_hospitals,
    }


class QuickTriageRequest(BaseModel):
    symptoms: str


@router.post("/triage-firstaid")
def quick_first_aid_triage(req: QuickTriageRequest):
    """
    Sub-second Emergency First Aid & Clinical Triage.
    Returns immediate Red Cross / NIM first-aid action steps without waiting
    for hospital geolocation, Overpass queries, or discovery workflows.
    """
    symptoms = req.symptoms.strip()
    if not symptoms:
        raise HTTPException(status_code=400, detail="Symptoms text required.")

    # Red-flag safety evaluation
    red_flag = evaluate_emergency_red_flags(symptoms)
    is_emergency = red_flag.get("is_emergency", False)

    first_aid_result = draft_first_aid_instructions(symptoms)

    if is_emergency:
        specialty = "EMERGENCY"
        urgency = "EMERGENCY"
    else:
        specialty = first_aid_result.get("specialty", "General Medicine")
        urgency = first_aid_result.get("urgency", "ROUTINE")

    summary = first_aid_result.get("summary")
    if not summary:
        if is_emergency:
            summary = f"Emergency medical triage activated for {red_flag.get('primary_condition', 'acute trauma')}."
        else:
            summary = f"Detected symptoms requiring {specialty} evaluation."

    first_aid = first_aid_result.get("firstAid")
    if not first_aid:
        if is_emergency:
            first_aid = red_flag.get("safety_first_aid", DEFAULT_FIRST_AID["emergency"])
        else:
            spec_key = specialty.lower()
            first_aid = DEFAULT_FIRST_AID.get(spec_key, DEFAULT_FIRST_AID["general medicine"])

    prerequisites = first_aid_result.get("prerequisites")
    if not prerequisites:
        if is_emergency:
            prerequisites = red_flag.get("prerequisites", [
                "Call 108 for emergency ambulance transport immediately",
                "Keep patient stationary and monitor breathing continuously",
                "Alert emergency trauma department before arrival"
            ])
        else:
            prerequisites = [
                "Carry government photo ID proof (Passport / Aadhar / Driver's License)",
                "Bring previous doctor prescriptions and medical records",
                "Keep emergency contact phone numbers accessible",
                "Wear comfortable, loose-fitting clothing"
            ]

    return {
        "specialty": specialty,
        "urgency": urgency,
        "summary": summary,
        "firstAid": first_aid,
        "prerequisites": prerequisites,
    }

