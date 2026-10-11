import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def get_nim_api_key() -> str:
    return os.getenv("NVIDIA_NIM_API_KEY", "")


def query_gemini_search(query: str, timeout: int = 25) -> Optional[str]:
    """
    Fallback web search using gemini-search-mcp (Google AI Mode via CDP/undetected).
    """
    try:
        import sys
        mcp_path = r"C:\Users\ralph\.gemini\antigravity-ide\mcp\gemini-search-mcp"
        if mcp_path not in sys.path:
            sys.path.insert(0, mcp_path)
        from gemini_search.engine import AIModeEngine
        import asyncio

        async def _run():
            engine = AIModeEngine()
            try:
                # Try visible or headless
                await engine.start(headless=True)
                return await engine.ask(query, timeout_ms=timeout * 1000)
            finally:
                await engine.stop()

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"gemini-search fallback attempt failed: {e}")
        return None



def parse_structured_hospital_fields(raw_text: str, hospital_name: str = "") -> Dict[str, Any]:
    """
    Parses phone, emergency_phone, website, emergency_available,
    speciality, tier, rating, services, amenities from AI text/search results.
    """
    result: Dict[str, Any] = {
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

    # 1. Regex fallbacks
    # Website
    web_match = re.search(r'(https?://[^\s)\]"\']+)', raw_text)
    if web_match:
        url = web_match.group(1).rstrip("./,")
        if not any(b in url for b in ["google.com", "gstatic.com", "policies.google", "support.google"]):
            result["website"] = url

    # Phone numbers
    phone_candidates = re.findall(r'(?:\+?91[\s-]?)?(?:0?[1-9]\d{1,4}[\s-]?)?\d{6,8}', raw_text)
    valid_phones = []
    for p in phone_candidates:
        d = re.sub(r'\D', '', p)
        if len(d) >= 10:
            valid_phones.append(p.strip())
    if valid_phones:
        result["phone"] = valid_phones[0]
        if len(valid_phones) > 1:
            result["emergency_phone"] = valid_phones[1]

    # Emergency available check
    low = raw_text.lower()
    if any(term in low for term in ["24/7", "24 hours", "emergency ward", "trauma center", "casualty", "emergency care"]):
        result["emergency_available"] = True

    # Rating
    rating_match = re.search(r'([1-5](?:\.\d)?)\s*(?:stars?|/5|\sout of 5)', raw_text, re.IGNORECASE)
    if rating_match:
        try:
            result["rating"] = float(rating_match.group(1))
        except ValueError:
            pass

    return result


def extract_batch_structured_hospitals(
    hospitals_input: List[Dict[str, str]],
    context_text: str = ""
) -> List[Dict[str, Any]]:
    """
    Given a list of hospital items [{'name': ..., 'location': ...}],
    uses AI to produce the exact structured JSON object for each hospital:
    - phone
    - emergency_phone
    - website
    - emergency_available
    - speciality
    - tier
    - rating
    - services
    - amenities
    """
    hospitals_json_str = json.dumps(hospitals_input, indent=2)

    prompt = f"""You are an expert medical database auditor. Given the following hospital(s) with their names and locations, research and generate real, accurate, and structured data for each hospital.

HOSPITALS LIST:
{hospitals_json_str}

OPTIONAL GROUNDING CONTEXT (e.g. from Google search):
\"\"\"
{context_text[:4000]}
\"\"\"

For each hospital in the list, produce EXACTLY the following structured fields:
1. "name": The hospital name as provided.
2. "phone": Main contact phone number with STD/country code (or null if unknown).
3. "emergency_phone": 24/7 casualty/ambulance emergency line (or null).
4. "website": Official hospital website URL (or null).
5. "emergency_available": Boolean (true if 24/7 emergency/trauma care is present, false otherwise).
6. "speciality": Comma-separated top medical specialties (e.g. "Cardiology, Orthopaedics, Neurology, Oncology, Paediatrics").
7. "tier": Hospital tier and classification (e.g. "Tier 1 - Quaternary Multi-Speciality", "Tier 2 - Secondary Care Hospital", "Daycare Urgent Clinic").
8. "rating": Real Google/Practo user review rating as a float between 1.0 and 5.0 (e.g. 4.4, or null).
9. "services": Comma-separated list of major clinical facilities & diagnostics (e.g. "ICU, NICU, Dialysis, Cath Lab, 24/7 Pharmacy, MRI, CT Scan").
10. "amenities": Comma-separated patient amenities (e.g. "Cashless TPA Insurance Desk, Private Deluxe Rooms, Cafeteria, Ambulance Service, Wheelchair Accessible").

Return ONLY a valid JSON list of objects matching the above schema. Do NOT include markdown code blocks, explanation or preamble."""

    nim_key = get_nim_api_key()
    if nim_key:
        try:
            resp = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {nim_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "meta/llama-3.2-11b-vision-instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 1500
                },
                timeout=45
            )
            if resp.status_code == 200:
                raw_out = resp.json()["choices"][0]["message"]["content"].strip()
                # strip code fences if present
                raw_out = re.sub(r'^```(?:json)?\s*', '', raw_out, flags=re.MULTILINE)
                raw_out = re.sub(r'```$', '', raw_out, flags=re.MULTILINE).strip()
                parsed = json.loads(raw_out)
                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "hospitals" in parsed:
                    return parsed["hospitals"]
                elif isinstance(parsed, dict):
                    return [parsed]
        except Exception as e:
            logger.warning(f"Batch AI structuring call failed: {e}")

    # Fallback to local parsing
    return [
        {
            "name": h.get("name"),
            **parse_structured_hospital_fields(context_text, h.get("name", ""))
        }
        for h in hospitals_input
    ]
