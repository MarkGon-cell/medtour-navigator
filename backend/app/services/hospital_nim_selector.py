"""
Module 3: NVIDIA NIM 7-Hospital Symptom Matcher & Tiers
Selects the top 7 hospitals that can properly treat the patient's symptoms.
Designates the top 2 as 'best' (clinical capability) and 'nearest' (safely reachable walk-in).
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from app.api.hybrid_first_aid_retriever import nim_generate_json

logger = logging.getLogger(__name__)

def select_and_tier_seven_hospitals(
    symptoms: str,
    specialty: str,
    urgency: str,
    candidates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Asks NVIDIA NIM to select 7 hospitals that can properly treat what the patient feels.
    Designates the top 2 as 'best' and 'nearest', with up to 5 'nearby' options.
    """
    api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not candidates:
        return []

    # Send up to 15 filtered candidates to the LLM
    top_candidates = candidates[:15]
    slim_candidates = [
        {
            "name": h.get("name"),
            "distance_km": round(h.get("distance_km", 0.0), 2),
            "address": h.get("address"),
            "specialties": h.get("specialties"),
            "facilities": h.get("facilities"),
            "emergency_available": h.get("emergency_available", False),
        }
        for h in top_candidates
    ]

    system_prompt = (
        "You are an elite clinical triage officer and hospital matching engine in India.\n"
        "Your goal is to select EXACTLY 7 hospitals from the candidates that will PROPERLY TREAT the patient's condition.\n\n"
        "STRICT CLINICAL RULES:\n"
        "1. NEVER recommend an Eye Clinic, Urology Clinic, Dental Clinic, or Skin Clinic for general medical complaints "
        "like food poisoning, fever, acute vomiting, dehydration, or chest pain.\n"
        "2. Prioritize General Hospitals, Multispeciality Hospitals, and Verified 24/7 Casualty centers.\n"
        "3. Designate exactly ONE 'best' hospital (highest clinical treatment capability, ICU, specialist).\n"
        "4. Designate exactly ONE 'nearest' hospital (closest physical distance that is CAPABLE of treating the symptoms).\n"
        "5. Designate the remaining up to 5 as 'nearby'.\n\n"
        "OUTPUT FORMAT: Return strictly valid JSON:\n"
        "{\n"
        '  "matched_hospitals": [\n'
        '    {\n'
        '      "name": "<exact name from candidates>",\n'
        '      "tier": "best"|"nearest"|"nearby",\n'
        '      "ai_match_score": 95,\n'
        '      "ai_match_reason": "Specific 8-15 word explanation of why this hospital can treat the patient"\n'
        '    }\n'
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"PATIENT SYMPTOMS: {symptoms}\n"
        f"DIAGNOSED SPECIALTY: {specialty}\n"
        f"URGENCY LEVEL: {urgency}\n\n"
        f"CANDIDATES (JSON):\n{json.dumps(slim_candidates, ensure_ascii=False)}"
    )

    selected = None
    if api_key:
        try:
            selected = nim_generate_json(
                api_key=api_key,
                system_prompt=system_prompt,
                user_message=user_prompt,
                expect_key="matched_hospitals",
                per_model_timeout=8.0,
                max_retries=1
            )
        except Exception as e:
            logger.warning(f"NIM 7-hospital selection failed: {e}")

    final_hospitals: List[Dict[str, Any]] = []
    used_indices = set()

    if selected and isinstance(selected.get("matched_hospitals"), list):
        for item in selected["matched_hospitals"]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            name_lower = str(item["name"]).strip().lower()
            
            # Find candidate match
            matched_cand = None
            matched_idx = -1
            for idx, cand in enumerate(top_candidates):
                if idx not in used_indices and (cand.get("name") or "").strip().lower() == name_lower:
                    matched_cand = cand
                    matched_idx = idx
                    break
            
            if matched_cand:
                h_copy = dict(matched_cand)
                h_copy["tier"] = item.get("tier", "nearby")
                h_copy["ai_match_score"] = int(item.get("ai_match_score", 85))
                h_copy["ai_match_reason"] = item.get("ai_match_reason", "Verified treatment facility")
                final_hospitals.append(h_copy)
                used_indices.add(matched_idx)

    # If LLM didn't return a full 7, fill with remaining candidates
    for idx, cand in enumerate(top_candidates):
        if idx not in used_indices and len(final_hospitals) < 7:
            h_copy = dict(cand)
            h_copy["tier"] = "nearby"
            h_copy["ai_match_score"] = 70
            h_copy["ai_match_reason"] = "Nearby facility in immediate radius"
            final_hospitals.append(h_copy)
            used_indices.add(idx)

    # Guarantee one 'best' and one 'nearest'
    if final_hospitals:
        if not any(h.get("tier") == "best" for h in final_hospitals):
            final_hospitals[0]["tier"] = "best"
        if not any(h.get("tier") == "nearest" for h in final_hospitals):
            # Pick closest distance among the 7
            nearest_idx = min(range(len(final_hospitals)), key=lambda i: final_hospitals[i].get("distance_km", 999))
            if final_hospitals[nearest_idx].get("tier") != "best":
                final_hospitals[nearest_idx]["tier"] = "nearest"
            elif len(final_hospitals) > 1:
                final_hospitals[1]["tier"] = "nearest"

    return final_hospitals[:7]
