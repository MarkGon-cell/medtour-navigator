import os
import re
import sys
import json
import concurrent.futures
from math import radians, sin, cos, sqrt, atan2
from typing import Optional, List, Dict, Any, Tuple
from fastapi import APIRouter, Depends
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
from app.api.hybrid_first_aid_retriever import parallel_nim_first_aid

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
                "You are an Emergency First Aid Dispatch AI.\n"
                "You provide life-saving, clear, numbered layperson action steps based STRICTLY on the provided Red Cross Medical Manual Excerpt.\n\n"
                "CRITICAL RULES:\n"
                "1. Base your steps directly on the provided manual excerpt.\n"
                "2. If the condition is an acute emergency (choking, severe bleeding, deep burns), NEVER suggest routine self-care (e.g. drinking fluids, taking paracetamol, or sprain RICE).\n"
                "3. Output clear, numbered actions in chronological order of life-saving priority.\n"
                "4. Output ONLY a raw JSON object (no markdown fences) with keys:\n"
                "- specialty: string (e.g. 'EMERGENCY' or 'CARDIOLOGY')\n"
                "- urgency: 'EMERGENCY'|'URGENT'|'ROUTINE'\n"
                "- summary: 1 concise sentence explaining the immediate emergency\n"
                "- firstAid: list of 4-6 direct operational first-aid action steps\n"
                "- prerequisites: list of 3-4 hospital arrival/transport preparation items\n\n"
                f"{rc_context if rc_context else ''}"
            )

            # Fire parallel NIM calls (staggered 1.6s to respect 40 RPM limit)
            nim_result = parallel_nim_first_aid(
                api_key=api_key,
                system_prompt=system_prompt,
                user_message=f"PATIENT EMERGENCY COMPLAINT: {symptoms}",
                n_parallel=3,
                per_model_timeout=5.0
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

    # High-accuracy fallback mapped to Red Cross emergency protocols
    specialty = "general medicine"
    for kw, spec in SYMPTOM_SPECIALTY_MAP.items():
        if kw in symptoms.lower():
            specialty = spec
            break

    first_aid = DEFAULT_FIRST_AID.get(specialty, DEFAULT_FIRST_AID["general medicine"])
    prerequisites = [
        "Carry valid Government Photo ID proof (Aadhar/PAN/Passport)",
        "Carry past medical records, prescription slips, or discharge summaries",
        "Keep emergency contact numbers handy",
        "Wear comfortable, loose clothing"
    ]
    urgency = "URGENT" if specialty in ["cardiology", "emergency", "neurology"] else "ROUTINE"
    summary = f"Detected symptoms requiring {specialty} medical evaluation."

    return {
        "specialty": specialty,
        "urgency": urgency,
        "summary": summary,
        "firstAid": first_aid,
        "prerequisites": prerequisites
    }


# ==========================================================
# PARALLEL CALL 2: AI INDEXING & HOSPITAL RECOMMENDATIONS
# ==========================================================
def score_and_rank_hospitals(
    symptoms: str,
    target_specialty: str,
    hospital_candidates: List[Dict[str, Any]],
    radius_km: float
) -> List[Dict[str, Any]]:
    """Evaluates and scores nearby hospitals for the specific patient symptoms."""
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

        score = 45  # Baseline
        reasons = []

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
                score += 35
                reasons.append(f"Specialized {target_specialty.title()} department")
            elif any(k in specs for k in ["multispecialty", "general"]):
                score += 15
                reasons.append("Multispecialty hospital")

            if h.get("emergency_available"):
                score += 10
                reasons.append("Emergency services available")

            if "icu" in facs or "critical" in facs:
                score += 5
                reasons.append("ICU facility")

        # Proximity score
        if dist < 3.0:
            score += 10
            reasons.append(f"Immediate proximity ({dist:.1f} km)")
        elif dist < 8.0:
            score += 5
            reasons.append(f"Nearby distance ({dist:.1f} km)")

        final_score = min(99, score)
        match_reason = " • ".join(reasons) if reasons else "Reachable medical center"

        if final_score >= 50:
            h_copy = dict(h)
            h_copy["ai_match_score"] = final_score
            h_copy["ai_match_reason"] = match_reason
            scored_hospitals.append(h_copy)
            seen_hospital_ids.add(h_id)

    scored_hospitals.sort(key=lambda x: (-x["ai_match_score"], x["distance_km"]))
    
    # Ensure at least nearest hospitals are shown if none hit 50%
    if not scored_hospitals:
        hospital_candidates.sort(key=lambda x: x["distance_km"])
        for h in hospital_candidates[:3]:
            if h.get("id") not in seen_hospital_ids:
                h_copy = dict(h)
                h_copy["ai_match_score"] = 50
                h_copy["ai_match_reason"] = "Nearest available facility"
                scored_hospitals.append(h_copy)
                seen_hospital_ids.add(h.get("id"))

    return scored_hospitals[:10]


@router.post("/analyze")
def analyze_symptoms(
    req: SymptomAnalysisRequest,
    db: Session = Depends(get_db),
):
    symptoms = req.symptoms
    lat = req.latitude
    lon = req.longitude
    radius_km = req.radius_km or 20.0

    # 1. Fetch geographic candidate hospitals from DB and deduplicate by name + location
    all_hospitals = db.query(Hospital).all()
    candidates = []
    seen_keys = set()

    for h in all_hospitals:
        if h.latitude and h.longitude:
            dist = haversine(lat, lon, h.latitude, h.longitude)
            if dist <= radius_km:
                # Deduplication key across name and approximate coordinates
                name_clean = re.sub(r'[^a-z0-9]', '', (h.name or "").lower())
                city_clean = re.sub(r'[^a-z0-9]', '', (h.city or h.district or "").lower())
                dedup_key = (name_clean, city_clean, round(h.latitude, 3), round(h.longitude, 3))
                if dedup_key in seen_keys or h.id in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                seen_keys.add(h.id)

                # Clean and deduplicate specialties for this hospital
                cleaned_specs = ""
                if h.specialties:
                    raw_specs = [s.strip() for s in re.split(r'\\n|\n|,|;', h.specialties) if s.strip()]
                    unique_specs = []
                    seen_spec = set()
                    for sp in raw_specs:
                        sp_title = sp.title()
                        if sp_title.lower() not in seen_spec:
                            seen_spec.add(sp_title.lower())
                            unique_specs.append(sp_title)
                    cleaned_specs = ", ".join(unique_specs)

                candidates.append({
                    "id": h.id,
                    "name": h.name,
                    "city": h.city,
                    "state": h.state,
                    "district": h.district,
                    "address": h.address,
                    "pincode": h.pincode,
                    "latitude": h.latitude,
                    "longitude": h.longitude,
                    "specialties": cleaned_specs,
                    "facilities": h.facilities,
                    "emergency_available": h.emergency_available,
                    "emergency_services": h.emergency_services,
                    "emergency_phone": h.emergency_phone if hasattr(h, "emergency_phone") else None,
                    "phone": h.phone,
                    "website": h.website,
                    "total_beds": h.total_beds,
                    "distance_km": round(dist, 2),
                })

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

    # 2. Execute Two Parallel Tasks Concurrently
    # Task 1: Draft First Aid Instructions (NVIDIA NIM / Red Cross Manual)
    # Task 2: AI Hospital Recommendation & Indexing
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_first_aid = executor.submit(draft_first_aid_instructions, symptoms)
        future_hospitals = executor.submit(score_and_rank_hospitals, symptoms, primary_specialty, candidates, radius_km)

        try:
            first_aid_result = future_first_aid.result(timeout=4.0)
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
            recommended_hospitals = future_hospitals.result(timeout=3.0)
        except concurrent.futures.TimeoutError:
            recommended_hospitals = []

    spec_res = (first_aid_result.get("specialty") or primary_specialty).lower()
    if is_emergency:
        specialty = "EMERGENCY"
        urgency = "EMERGENCY"
    else:
        specialty = first_aid_result.get("specialty", primary_specialty.title())
        urgency = first_aid_result.get("urgency", "ROUTINE")

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
