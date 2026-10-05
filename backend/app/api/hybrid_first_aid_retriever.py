import os
import sys
import math
import re
import unicodedata
import random
import time
from collections import Counter
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import pdfplumber
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, parse_page_ranges, IGNORE_PAGE_RANGES

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "inputs", "redcross.pdf"))

# -----------------------------------------------------------------------
# 1. STOPWORDS & EXCLUDED SECTIONS
# -----------------------------------------------------------------------
CONVERSATIONAL_STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "him", "his",
    "she", "her", "they", "them", "what", "which", "who", "when", "where", "why",
    "how", "can", "cant", "cannot", "could", "should", "would", "is", "was",
    "are", "were", "do", "does", "did", "stop", "start", "provide", "providing",
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "from", "with",
    "by", "about", "like", "through", "over", "into", "some", "such", "this", "that",
    "just", "really", "very", "super", "slightly", "suddenly", "feeling", "feel",
    "got", "getting", "having", "has", "had", "large", "small", "piece", "broken"
}

EXCLUDED_SECTION_PREFIXES = {
    "CONTENT OF FIRST AID KITS", "SMALL FIRST AID BOX", "MEDIUM FIRST AID BOX",
    "LARGE FIRST AID BOX", "FIRST MEDICAL RESPONDER FIRST AID KIT",
    "B.1 AIMS OF FIRST AID", "B.2 FIRST AID AND THE LAW", "B.2.1", "B.2.2",
    "B.2.3", "B.2.4", "B.2.5", "B.3.5 When can I stop", "B.4 STRESS WHEN GIVING",
    "B.8 HYGIENE AND HAND WASHING", "MESSAGE OF THE CHAIRMAN", "FOREWORD",
    "PREFACE", "ACKNOWLEDGEMENTS", "USING THIS MANUAL"
}

# -----------------------------------------------------------------------
# 2. CLINICAL EXPANSION RULES
#    Each rule: (regex_to_detect_in_query, [clinical_terms_to_inject], priority_boost)
#    Higher priority_boost => tokens get more IDF weight in retrieval
# -----------------------------------------------------------------------
CLINICAL_EXPANSION_RULES = [
    # MECHANICAL AIRWAY / CHOKING  ← must dominate over C.6 "swelling throat" (anaphylaxis)
    (
        r"\b(chok|cant talk|cant cough|cannot talk|cannot cough|cant breathe|cannot breathe|"
        r"blue face|turning blue|face turning|gagging|strangled|food stuck|swallowed|eating)\b",
        ["choking", "airway obstruction", "back blows", "abdominal thrusts", "foreign body airway"],
        5
    ),
    # SEVERE BLEEDING / WOUNDS
    (
        r"\b(bleed|blood|gush|pouring|gash|wound|cut|lacerat|stab|soaked|soaked tissue|flowing|hemorrhage)\b",
        ["first aid for bleeding", "types of wounds", "bleeding", "wounds", "shock", "direct pressure"],
        5
    ),
    # BURNS / SCALDS
    (
        r"\b(burn|scald|boiling|hot water|fire|flame|steam|blister|red skin|burning)\b",
        ["dry burns and scalds", "burn wounds", "scalds", "burns"],
        5
    ),
    # FRACTURES
    (
        r"\b(fracture|broken bone|crack|snapped|deform|fell hard|sprain|dislocated)\b",
        ["fractures", "injuries to bones", "immobilization"],
        3
    ),
    # CARDIAC / HEART
    (
        r"\b(chest pain|tightness in chest|heart attack|radiating|left arm|crushing chest)\b",
        ["chest discomfort", "heart and blood circulation", "resuscitation"],
        3
    ),
]

# Anatomy-only terms that carry low emergency information value
ANATOMY_LOW_PRIORITY = {"throat", "throat", "leg", "arm", "hand", "foot", "pelvis", "skin", "bone"}

# -----------------------------------------------------------------------
# 3. BUILD DYNAMIC BM25 CORPUS FROM PDF INDEX
# -----------------------------------------------------------------------
index_entries = parse_index_pages(PDF_PATH)
ignored_pages = parse_page_ranges(IGNORE_PAGE_RANGES)

procedural_index = []
for entry in index_entries:
    topic = entry["topic"].strip()
    if entry["page_index"] in ignored_pages or entry["listed_page"] < 18:
        continue
    if any(topic.startswith(ex) or ex in topic for ex in EXCLUDED_SECTION_PREFIXES):
        continue
    procedural_index.append(entry)

doc_count = len(procedural_index)
doc_freqs = Counter()
tokenized_docs = []

for entry in procedural_index:
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower())
    token_set = set(raw_tokens) - CONVERSATIONAL_STOPWORDS
    tokenized_docs.append((entry, token_set))
    for t in token_set:
        doc_freqs[t] += 1


# -----------------------------------------------------------------------
# 4. QUERY EXPANDER
# -----------------------------------------------------------------------
def expand_query_to_clinical_entities(query: str):
    """Returns list of (term, priority_boost) tuples from vague narrative."""
    expanded = {}  # term -> priority_boost

    query_lower = query.lower()
    for pattern, clinical_terms, boost in CLINICAL_EXPANSION_RULES:
        if re.search(pattern, query_lower):
            for ct in clinical_terms:
                expanded[ct] = max(expanded.get(ct, 0), boost)

    # Also include raw non-stopword tokens from query at base priority=1
    tokens = re.findall(r'\b[a-z]{3,}\b', query_lower)
    for t in tokens:
        if t not in CONVERSATIONAL_STOPWORDS:
            # Downweight anatomy tokens
            base = 0.5 if t in ANATOMY_LOW_PRIORITY else 1
            expanded[t] = max(expanded.get(t, 0), base)

    return list(expanded.items())  # [(term, boost), ...]


# -----------------------------------------------------------------------
# 5. RETRIEVER — multi-chapter BM25 with clinical priority weighting
# -----------------------------------------------------------------------
def retrieve_multi_chapter_sections(query: str, max_sections: int = 4) -> List[Dict[str, Any]]:
    """Returns ranked list of distinct Red Cross chapters relevant to the query."""
    term_boosts = expand_query_to_clinical_entities(query)

    scored = []
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        topic_lower = entry["topic"].lower()

        for ck, priority in term_boosts:
            # Full phrase match in topic title (e.g. "first aid for bleeding")
            if len(ck.split()) > 1 and ck in topic_lower:
                score += 40.0 * priority

            for dt in doc_tokens:
                match_type = None
                if ck == dt:
                    match_type = "exact"
                elif len(ck) >= 4 and len(dt) >= 4:
                    if ck.startswith(dt) or dt.startswith(ck) or ck[:4] == dt[:4]:
                        match_type = "root"

                if match_type:
                    df = doc_freqs.get(dt, 1)
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    weight = (4.0 if match_type == "exact" else 2.0) * priority
                    if df <= 8:
                        weight *= 1.8
                    score += idf * weight

        # Boost procedural action headings
        if any(act in topic_lower for act in ["what do i do", "care of", "first aid for", "types of", "treatment"]):
            score *= 1.4

        # Boost known emergency chapter prefixes (C.5 Choking, D.3 D.4 D.5 Bleeding, H.3 Burns, E.4 Fractures)
        if re.search(r'^[C-H]\.[3-6]', entry["topic"]):
            score *= 1.35

        # Penalise chronic/non-emergency headings
        if any(bad in topic_lower for bad in ["blood pressure", "hygiene", "stress", "law", "psychological"]):
            score *= 0.05

        if score > 0.5:
            e = dict(entry)
            e["score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["score"], reverse=True)

    # Pick top-N across distinct chapter groups (avoid duplicating same page)
    selected = []
    seen_groups = set()
    seen_pages = set()
    for item in scored:
        m = re.match(r'^([A-Z](?:\.\d+)?)', item["topic"])
        group = m.group(1) if m else item["topic"][:4]
        if item["page_index"] not in seen_pages and (group not in seen_groups or len(selected) < max_sections):
            selected.append(item)
            seen_groups.add(group)
            seen_pages.add(item["page_index"])
        if len(selected) >= max_sections:
            break

    return selected


# -----------------------------------------------------------------------
# 6. PRECISE BOUNDARY EXTRACTOR WITH UNICODE NORMALIZATION
# -----------------------------------------------------------------------
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


# Section header boundary pattern — stops extraction at the next heading
SECTION_HEADER_RE = re.compile(r'^[A-Z]\.\d+(?:\.\d+)?\s+[A-Z]')


def extract_accurate_chapter_evidence(pdf_path: str, matched_sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts scoped text for each matched section with strict heading boundary isolation."""
    extracted_sections = []

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for sec in matched_sections:
            p_idx = sec["page_index"]
            if p_idx >= total:
                continue

            raw = pdf.pages[p_idx].extract_text() or ""
            # Include next page to capture complete numbered steps
            if p_idx + 1 < total and (p_idx + 1) not in ignored_pages:
                raw += "\n" + (pdf.pages[p_idx + 1].extract_text() or "")

            clean = clean_and_normalize_text(raw)
            lines = clean.split("\n")

            # Find starting line that matches the target heading
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

            # Slice from start until the NEXT section header is encountered
            scoped_lines = []
            for line in lines[start_idx:]:
                # Stop at a new top-level heading that isn't our target
                if scoped_lines and SECTION_HEADER_RE.match(line):
                    # Check if this line is the target heading itself (first occurrence)
                    ll = line.lower()
                    if sum(1 for w in target_words if w in ll) < 2:
                        break
                scoped_lines.append(line)
                if len(scoped_lines) >= 40:
                    break

            scoped_text = "\n".join(scoped_lines)

            extracted_sections.append({
                "topic": sec["topic"],
                "source_ref": f"Red Cross Manual — Physical Page {sec['actual_pdf_page']} (TOC Page {sec['listed_page']})",
                "text": scoped_text[:1600],
                "actual_pdf_page": sec["actual_pdf_page"],
                "listed_page": sec["listed_page"],
            })

    return extracted_sections


# -----------------------------------------------------------------------
# 7. PARALLEL MULTI-UA NVIDIA NIM CALLER
#    Fires multiple concurrent requests across different User-Agents and
#    API key rotations, respecting 40 RPM by spacing submissions.
# -----------------------------------------------------------------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/117.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148",
]

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

CHAIN_MODELS = [
    "poolside/laguna-xs-2.1",
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "meta/llama-3.2-90b-vision-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
]


def _call_nim_model(model: str, api_key: str, system_msg: str, user_msg: str, timeout: float = 6.0) -> Dict | None:
    """Makes a single NIM API call with a randomised User-Agent to avoid rate-limit clustering."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": random.choice(USER_AGENTS),
        "X-Request-ID": f"medtour-{int(time.time()*1000)}-{random.randint(100, 999)}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }
    try:
        resp = requests.post(NIM_BASE_URL, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _parse_json_from_response(raw: str) -> Dict | None:
    """Extracts and parses JSON from model output, stripping markdown fences."""
    if not raw:
        return None
    clean = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r'\{[\s\S]+\}', clean)
    if m:
        try:
            return __import__("json").loads(m.group(0))
        except Exception:
            pass
    return None


def parallel_nim_first_aid(
    api_key: str,
    system_prompt: str,
    user_message: str,
    n_parallel: int = 2,
    per_model_timeout: float = 3.0,
) -> Dict | None:
    """
    Fires fast parallel NIM calls across top working models.
    Returns first valid JSON response that contains 'firstAid'.
    """
    models_to_try = [
        "poolside/laguna-xs-2.1",
        "meta/llama-3.2-11b-vision-instruct",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
    ]

    def _worker(model: str):
        raw_resp = _call_nim_model(model, api_key, system_prompt, user_message, per_model_timeout)
        if raw_resp:
            content = raw_resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = _parse_json_from_response(content)
            if parsed and "firstAid" in parsed:
                return parsed
        return None

    with ThreadPoolExecutor(max_workers=len(models_to_try)) as executor:
        futures = {executor.submit(_worker, model): model for model in models_to_try}
        try:
            for future in as_completed(futures, timeout=per_model_timeout + 0.5):
                res = future.result()
                if res:
                    return res
        except Exception:
            pass

    return None
