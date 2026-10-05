import os
import sys
import re
import math
import unicodedata
from collections import Counter
from typing import List, Dict, Any, Tuple
import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, parse_page_ranges, IGNORE_PAGE_RANGES

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "inputs", "redcross.pdf"))

# =========================================================================
# PHASE 1: DETERMINISTIC SAFETY RED-FLAG FILTER
# =========================================================================
RED_FLAG_PATTERNS = {
    "CHOKING_AIRWAY": {
        "patterns": [
            r"\b(can'?t|cannot) (breathe|talk|speak|cough)\b",
            r"\b(turning|turned) blue\b",
            r"\bgrabbed (his|her|my) throat\b",
            r"\bchoking\b",
            r"\bforeign object in (airway|throat)\b",
            r"\bfood stuck\b",
            r"\bgagging\b",
        ],
        "primary_condition": "Acute Airway Obstruction / Choking",
        "canonical_terms": ["choking", "what do i do in case a person is choking", "airway obstruction", "back blows", "abdominal thrusts"],
        "specialty": "EMERGENCY",
        "urgency": "EMERGENCY",
        "priority_toc_target": "C.5",
        "safety_first_aid": [
            "Act immediately: Ask 'Are you choking?' If they cannot speak or cough, lean them forward.",
            "Give up to 5 sharp back blows between the shoulder blades using the heel of your hand.",
            "If back blows fail, stand behind them, place a fist above the navel, and deliver up to 5 quick inward and upward abdominal thrusts (Heimlich maneuver).",
            "Repeat alternating 5 back blows and 5 abdominal thrusts until the object dislodges.",
            "If the person becomes unresponsive, lower them to the floor, call 108/EMS immediately, and begin CPR with chest compressions."
        ],
        "prerequisites": [
            "Call 108 / Emergency Medical Services immediately if object does not dislodge within 60 seconds",
            "Keep the airway clear and do not attempt blind finger sweeps in the mouth",
            "Prepare for immediate ambulance transport to nearest emergency trauma center"
        ]
    },
    "SEVERE_BLEEDING": {
        "patterns": [
            r"\b(blood|bleeding) (is )?gushing\b",
            r"\bspurting blood\b",
            r"\bsoaked (immediately|through)\b",
            r"\bdeep gash\b",
            r"\barterial bleeding\b",
            r"\bcopious bleeding\b",
            r"\bgushing rapidly\b",
            r"\bpouring out\b",
        ],
        "primary_condition": "Severe External Hemorrhage / Arterial Bleeding",
        "canonical_terms": ["first aid for bleeding (in general)", "types of bleeding", "types of wounds", "wounds", "shock"],
        "specialty": "EMERGENCY",
        "urgency": "EMERGENCY",
        "priority_toc_target": "D.4",
        "safety_first_aid": [
            "Apply firm, direct, continuous pressure over the wound using a clean sterile cloth or pad immediately.",
            "Do NOT remove or lift the cloth to check bleeding; if blood soaks through, add more layers firmly on top.",
            "Elevate the injured limb above the level of the heart if no bone fracture is suspected.",
            "Secure the pressure pad firmly with a tight bandage over the bleeding site.",
            "Keep the casualty lying down and cover with a blanket to prevent shock; monitor consciousness and breathing constantly until emergency teams arrive."
        ],
        "prerequisites": [
            "Dispatch emergency ambulance (108) immediately for uncontrolled blood loss",
            "Keep continuous pressure applied during transport; do NOT release bandage",
            "Note approximate time bleeding started and blood volume lost for the trauma surgeon"
        ]
    },
    "SEVERE_BURNS": {
        "patterns": [
            r"\b(boiling|hot) (water|oil|tea|liquid)\b",
            r"\bwatery bubbles\b",
            r"\bblisters? popping\b",
            r"\bthird degree burn\b",
            r"\bcharred skin\b",
            r"\bburning like fire\b",
            r"\bspilled hot\b",
        ],
        "primary_condition": "Partial/Full Thickness Thermal Burn (Scald)",
        "canonical_terms": ["dry burns and scalds", "burn wounds", "care of minor burns", "burns from flames"],
        "specialty": "EMERGENCY",
        "urgency": "EMERGENCY",
        "priority_toc_target": "H.3.4",
        "safety_first_aid": [
            "Immediately cool the burn under gentle, cool running tap water for at least 15 to 20 minutes.",
            "Gently remove constrictive clothing, rings, and watches from the injured limb before swelling starts (do NOT pull clothing adhered to the burn).",
            "Never apply ice, ice water, butter, toothpaste, turmeric, or oils to the burned area.",
            "Do NOT pop, pierce, or break any watery blisters; doing so drastically increases severe infection risk.",
            "Cover the cooled burn loosely with a sterile non-adherent dressing or clean plastic wrap (cling film) to protect exposed nerve endings."
        ],
        "prerequisites": [
            "Keep the burn site covered and clean during travel to hospital",
            "Do not apply any domestic ointments or home remedies before doctor inspects burn depth",
            "Bring details of the hot substance (boiling water/oil/chemical) for the burn care unit"
        ]
    },
    "CARDIAC_EMERGENCY": {
        "patterns": [
            r"\bcrushing chest pain\b",
            r"\btightness in (my|the) chest\b",
            r"\belephant sitting on (my|the) chest\b",
            r"\bchest pain radiating\b",
            r"\bheart attack\b",
        ],
        "primary_condition": "Acute Coronary Syndrome / Suspected Myocardial Infarction",
        "canonical_terms": ["chest discomfort", "heart and blood circulation", "resuscitation (basic cpr)"],
        "specialty": "CARDIOLOGY",
        "urgency": "EMERGENCY",
        "priority_toc_target": "D.",
        "safety_first_aid": [
            "Call 108 / Emergency Medical Services immediately without delay.",
            "Place the patient in a comfortable half-sitting position on the floor with head and shoulders supported (W-position).",
            "Loosen all tight clothing around neck, chest, and waist to ease breathing.",
            "Keep the patient completely calm and still; prohibit walking or physical exertion.",
            "If conscious and previously prescribed, assist them in taking emergency medication (e.g., Sorbitrate/Aspirin 300mg chewed) if not contraindicated."
        ],
        "prerequisites": [
            "Call 108 immediately for an Advanced Life Support (ALS) ambulance with ECG capability",
            "Gather all past cardiac prescriptions, prior ECG strips, and medical records",
            "Ensure emergency contacts and family are alerted immediately"
        ]
    }
}

def evaluate_emergency_red_flags(query: str) -> Dict[str, Any]:
    """Evaluates raw narrative against deterministic life-threatening clinical patterns."""
    normalized = query.lower()
    for category, meta in RED_FLAG_PATTERNS.items():
        for pat in meta["patterns"]:
            if re.search(pat, normalized):
                return {
                    "is_emergency": True,
                    "category": category,
                    "primary_condition": meta["primary_condition"],
                    "canonical_terms": meta["canonical_terms"],
                    "forced_specialty": meta["specialty"],
                    "forced_urgency": meta["urgency"],
                    "priority_toc_target": meta.get("priority_toc_target"),
                    "safety_first_aid": meta["safety_first_aid"],
                    "prerequisites": meta["prerequisites"]
                }
    return {"is_emergency": False}


# =========================================================================
# PHASE 2: CANONICAL CLINICAL ENTITY EXPANSION
# =========================================================================
CONVERSATIONAL_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "what", "which", "who", "when", "where", "why",
    "how", "can", "cant", "cannot", "could", "should", "would", "is", "was",
    "are", "were", "do", "does", "did", "stop", "start", "provide", "providing",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "from", "with",
    "by", "about", "like", "through", "over", "into", "some", "such", "this", "that",
    "just", "really", "very", "super", "slightly", "suddenly", "feeling", "feel",
    "got", "getting", "having", "has", "had", "large", "small", "piece", "broken",
    "stepped", "window", "uncle", "mutton", "eating", "spilled", "accidentally"
}

def expand_query_to_clinical_entities(query: str, red_flag: Dict[str, Any] = None) -> List[Tuple[str, float]]:
    """Maps narrative input into weighted medical search terms."""
    terms_map = {}
    
    if red_flag and red_flag.get("is_emergency"):
        for term in red_flag.get("canonical_terms", []):
            terms_map[term.lower()] = 10.0
            
    # Narrative medical terms
    q_low = query.lower()
    if re.search(r"\b(chok|throat|breathe|talk|cough|blue|airway)\b", q_low):
        for t in ["choking", "what do i do in case a person is choking", "airway", "respiratory"]:
            terms_map[t] = max(terms_map.get(t, 0), 8.0)
            
    if re.search(r"\b(bleed|blood|gush|wound|gash|cut|stab|soaked)\b", q_low):
        for t in ["first aid for bleeding (in general)", "bleeding", "types of wounds", "wounds", "shock"]:
            terms_map[t] = max(terms_map.get(t, 0), 8.0)
            
    if re.search(r"\b(burn|scald|boiling|hot|blister|bubbles|skin)\b", q_low):
        for t in ["dry burns and scalds", "burn wounds", "care of minor burns", "burns"]:
            terms_map[t] = max(terms_map.get(t, 0), 8.0)

    # Add remaining meaningful words
    tokens = re.findall(r'\b[a-z]{4,}\b', q_low)
    for tok in tokens:
        if tok not in CONVERSATIONAL_STOPWORDS:
            terms_map[tok] = max(terms_map.get(tok, 0), 1.0)
            
    return list(terms_map.items())


# =========================================================================
# PHASE 3: DEEP PROCEDURAL LEAF-NODE RETRIEVAL (BM25)
# =========================================================================
BLACKLIST_HEADING_PATTERNS = [
    r"LARGE FIRST AID BOX",
    r"SMALL FIRST AID BOX",
    r"MEDIUM FIRST AID BOX",
    r"FIRST MEDICAL RESPONDER",
    r"CONTENT OF FIRST AID KITS",
    r"FIRST AID AND THE LAW",
    r"AIMS OF FIRST AID",
    r"STRESS WHEN GIVING",
    r"HYGIENE AND HAND WASHING",
    r"WHEN CAN I STOP PROVIDING FIRST AID",
    r"MESSAGE OF THE CHAIRMAN",
    r"FOREWORD",
    r"PREFACE",
    r"ACKNOWLEDGEMENTS",
    r"USING THIS MANUAL",
    r"THE SKIN$",
    r"SKIN FUNCTIONS",
    r"THE HEART AND THE BLOOD CIRCULATION$",
    r"BLOOD PRESSURE",
    r"ANATOMY",
]

# Parse and clean index
raw_index = parse_index_pages(PDF_PATH)
ignored_pages = parse_page_ranges(IGNORE_PAGE_RANGES)

procedural_leaf_index = []
for entry in raw_index:
    topic = entry["topic"].strip()
    if entry["page_index"] in ignored_pages or entry["listed_page"] < 18:
        continue
    # Filter out broad introduction chapters & equipment boxes
    if any(re.search(pat, topic, re.IGNORECASE) for pat in BLACKLIST_HEADING_PATTERNS):
        continue
    # Exclude broad root chapter containers when searching for action procedures
    # e.g. "D. HEART, BLOOD CIRCULATION, SHOCK" or "C. RESPIRATORY SYSTEM AND BREATHING"
    if re.match(r'^[A-Z]\.\s+[A-Z,\s]+$', topic):
        continue
    procedural_leaf_index.append(entry)

doc_count = len(procedural_leaf_index)
doc_freqs = Counter()
tokenized_docs = []

for entry in procedural_leaf_index:
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower())
    token_set = set(raw_tokens) - CONVERSATIONAL_STOPWORDS
    tokenized_docs.append((entry, token_set))
    for t in token_set:
        doc_freqs[t] += 1


def retrieve_procedural_sections(query: str, max_sections: int = 3) -> List[Dict[str, Any]]:
    """Deep leaf-node procedural section retrieval."""
    red_flag = evaluate_emergency_red_flags(query)
    weighted_terms = expand_query_to_clinical_entities(query, red_flag)
    priority_prefix = red_flag.get("priority_toc_target") if red_flag.get("is_emergency") else None

    scored = []
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        topic_lower = entry["topic"].lower()

        # Deterministic prefix alignment (e.g. C.5 for choking, D.4 for bleeding)
        if priority_prefix and entry["topic"].startswith(priority_prefix):
            score += 150.0

        for term, weight in weighted_terms:
            # Phrase match in leaf topic heading
            if len(term.split()) > 1 and term in topic_lower:
                score += 50.0 * weight

            for dt in doc_tokens:
                match_type = None
                if term == dt:
                    match_type = "exact"
                elif len(term) >= 4 and len(dt) >= 4:
                    if term.startswith(dt) or dt.startswith(term) or term[:4] == dt[:4]:
                        match_type = "root"

                if match_type:
                    df = doc_freqs.get(dt, 1)
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    term_score = (4.0 if match_type == "exact" else 2.0) * weight
                    if df <= 6:
                        term_score *= 2.0
                    score += idf * term_score

        # Boost action procedural leaves ("What do I do", "Care of", "First aid for")
        if any(act in topic_lower for act in ["what do i do", "first aid for", "care of", "types of", "treatment"]):
            score *= 1.4

        if score > 1.0:
            e = dict(entry)
            e["score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Pick diverse top-N leaves
    selected = []
    seen_pages = set()
    for item in scored:
        if item["page_index"] not in seen_pages:
            selected.append(item)
            seen_pages.add(item["page_index"])
        if len(selected) >= max_sections:
            break

    return selected


# =========================================================================
# PHASE 4: PRECISE PDF BOUNDARY SLICER (Heading to next Heading)
# =========================================================================
def clean_and_normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.replace("\uf0a7", "*").replace("\uf0b7", "*")
    normalized = normalized.replace("\u2018", "'").replace("\u2019", "'")
    normalized = normalized.replace("\u201c", '"').replace("\u201d", '"')
    normalized = normalized.replace("\u2013", "-").replace("\u2014", "-")
    lines = [line.strip() for line in normalized.split("\n") if line.strip()]
    return "\n".join(lines)

SECTION_HEADER_RE = re.compile(r'^[A-Z]\.\d+(?:\.\d+)?\s+[A-Z]')

def extract_precise_leaf_evidence(pdf_path: str, matched_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts strictly bounded text between target heading and the next heading."""
    extracted = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for sec in matched_sections:
            p_idx = sec["page_index"]
            if p_idx >= total:
                continue

            raw = pdf.pages[p_idx].extract_text() or ""
            if p_idx + 1 < total and (p_idx + 1) not in ignored_pages:
                raw += "\n" + (pdf.pages[p_idx + 1].extract_text() or "")

            clean = clean_and_normalize_text(raw)
            lines = clean.split("\n")

            target_words = [
                w for w in re.findall(r'\b[a-z]{4,}\b', sec["topic"].lower())
                if w not in CONVERSATIONAL_STOPWORDS
            ][:4]

            start_idx = 0
            for i, line in enumerate(lines):
                ll = line.lower()
                if sum(1 for w in target_words if w in ll) >= min(2, len(target_words)):
                    start_idx = i
                    break

            scoped_lines = []
            for line in lines[start_idx:]:
                if scoped_lines and SECTION_HEADER_RE.match(line):
                    ll = line.lower()
                    if sum(1 for w in target_words if w in ll) < 2:
                        break
                scoped_lines.append(line)
                if len(scoped_lines) >= 35:
                    break

            scoped_text = "\n".join(scoped_lines)
            extracted.append({
                "topic": sec["topic"],
                "source_ref": f"Red Cross Manual Physical Pg {sec['actual_pdf_page']} (TOC Pg {sec['listed_page']})",
                "text": scoped_text[:1600],
                "actual_pdf_page": sec["actual_pdf_page"],
                "listed_page": sec["listed_page"],
            })
    return extracted
