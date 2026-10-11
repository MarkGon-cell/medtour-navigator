"""
Module 1: Clinical Specialty Guardrails & Exclusions
Filters out clinics that cannot handle the patient's acute symptoms
(e.g., Eye clinic or Urology clinic for food poisoning).
"""
import re
from typing import Dict, List, Any, Optional

# Keywords indicating specific single-specialty focus
SINGLE_SPECIALTY_FLAGS = {
    "ophthalmology": ["eye", "ophthal", "retina", "lasik", "vision", "cornea", "cataract"],
    "dentistry": ["dental", "dentist", "orthodont", "teeth", "oral care"],
    "dermatology": ["skin", "derma", "cosmetic", "hair", "laser", "aesthetic"],
    "urology": ["urology", "urologist", "kidney stone", "urinary", "andrology"],
    "ent": ["ent", "ear", "nose", "throat"],
    "fertility": ["ivf", "fertility", "maternity", "women hospital", "gynec"],
    "orthopedics_clinic": ["orthopedic center", "joint clinic", "bone center", "spine clinic"],
    "physiotherapy": ["physio", "rehab", "chiropractic"],
}

# Acute general medical conditions that CANNOT be sent to single-specialty clinics
ACUTE_SYSTEMIC_CONDITIONS = [
    "food poisoning", "gastro", "diarrhea", "vomiting", "stomach pain",
    "fever", "infection", "poisoning", "chest pain", "cardiac", "stroke",
    "shortness of breath", "breathing", "dehydration", "headache"
]

def is_single_focus_clinic(name: str, specialties: str = "", facilities: str = "") -> Optional[str]:
    """
    Checks if a facility name or specialty explicitly declares it as a single-specialty clinic.
    Returns the focused specialty if single-focus, or None if general/multispeciality.
    """
    combined = f"{name} {specialties} {facilities}".lower()
    
    # If explicitly declared as multispeciality or general hospital, not single-focus
    if any(w in combined for w in ["multi", "general", "tertiary", "trauma", "casualty", "district hospital", "civil hospital"]):
        return None
        
    for specialty, kws in SINGLE_SPECIALTY_FLAGS.items():
        for kw in kws:
            # Check whole word match or prominent name indicator
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, combined):
                return specialty
    return None

def filter_compatible_facilities(
    candidates: List[Dict[str, Any]],
    symptoms: str,
    target_specialty: str
) -> List[Dict[str, Any]]:
    """
    Enforces clinical compatibility guardrail:
    Disqualifies single-specialty clinics for mismatched acute conditions.
    """
    s_lower = symptoms.lower()
    t_lower = (target_specialty or "").lower()
    
    is_acute_systemic = any(c in s_lower for c in ACUTE_SYSTEMIC_CONDITIONS)
    
    compatible = []
    for h in candidates:
        name = h.get("name", "")
        specs = h.get("specialties", "") or ""
        facs = h.get("facilities", "") or ""
        has_247_er = h.get("emergency_available", False) or "24/7" in facs.lower() or "casualty" in facs.lower()
        
        focus = is_single_focus_clinic(name, specs, facs)
        
        # If it's food poisoning / general acute and the clinic is an eye/urology/dental clinic:
        if is_acute_systemic and focus and not has_247_er:
            # Hard exclusion
            continue
            
        # If patient has eye symptoms and it's an eye clinic, it's great!
        if focus and focus in t_lower:
            compatible.append(h)
            continue
            
        if focus and focus not in t_lower and not has_247_er:
            # Skip irrelevant specialty clinics
            continue
            
        compatible.append(h)
        
    # If the filter was too aggressive and removed all, keep candidates but prefer general/multi
    return compatible if compatible else candidates
