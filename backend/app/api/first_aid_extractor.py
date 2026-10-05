import os
import re
import json
import sys
from pydantic import BaseModel, Field
from typing import List, Tuple, Dict, Set
import pdfplumber
from pypdf import PdfReader
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ==========================================#
# 1. DEFINE STRICTLY STRUCTURED FIRST-AID SCHEMA#
# ==========================================

class FirstAidGuide(BaseModel):
    condition: str = Field(description="The medical emergency or condition name (e.g., Burns, Choking, CPR, Fracture, Bleeding).")
    emergency_severity: str = Field(description="Clear signs indicating if the user must call 108 / Emergency Medical Services immediately.")
    simple_summary: str = Field(description="A 1-2 sentence explanation of what is happening in clear, plain language.")
    action_steps: List[str] = Field(description="Numbered, active-voice, sequential steps on what to do right now.")
    what_to_avoid: List[str] = Field(description="Crucial dangerous actions or common mistakes to avoid.")
    source_location: str = Field(default="", description="Source page number and section within PDF.")


# ==========================================#
# 2. CONFIGURATION & PAGE RANGES#
# ==========================================

# Ignored pages in PDF (1-based)
IGNORE_PAGE_RANGES = "1-2, 11-18, 344-353"

# Index / Table of contents page range (1-based)
INDEX_PAGE_RANGES = "3-10"

# Offset to map index page number to actual physical PDF page (+2)
INDEX_TO_PDF_PAGE_OFFSET = 2


def parse_page_ranges(range_str: str, total_pages: int = 1000) -> Set[int]:
    """Parse comma-separated page ranges into 0-based page index set."""
    if not range_str.strip():
        return set()
    pages = set()
    parts = [p.strip() for p in range_str.split(",")]
    for part in parts:
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                start = max(1, start)
                end = min(total_pages, end)
                pages.update(range(start - 1, end))
            except ValueError:
                continue
        else:
            try:
                p_num = int(part)
                if 1 <= p_num <= total_pages:
                    pages.add(p_num - 1)
            except ValueError:
                continue
    return pages


# ==========================================#
# 3. INDEX PARSER (Pages 3-10)#
# ==========================================

def parse_index_pages(input_path: str) -> List[Dict]:
    """
    Reads pages 3-10 using pdfplumber, extracts topic lines and listed page numbers,
    and applies the +2 page offset to locate the actual physical PDF page.
    """
    index_entries = []
    
    with pdfplumber.open(input_path) as pdf:
        total = len(pdf.pages)
        # 0-based index for pages 3-10 is range(2, min(10, total))
        for page_idx in range(2, min(10, total)):
            text = pdf.pages[page_idx].extract_text() or ""
            lines = text.split("\n")
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                
                # Match pattern like: "Choking in adults ................. 45" or "Burns and Scalds 112"
                match = re.search(r'^(.*?)[.\s_–-]+(\d{1,3})\s*$', line_str)
                if match:
                    topic = match.group(1).strip(". ")
                    listed_page = int(match.group(2))
                    actual_pdf_page = listed_page + INDEX_TO_PDF_PAGE_OFFSET
                    if 1 <= actual_pdf_page <= total:
                        index_entries.append({
                            "topic": topic,
                            "listed_page": listed_page,
                            "actual_pdf_page": actual_pdf_page,
                            "page_index": actual_pdf_page - 1  # 0-based
                        })
                else:
                    words = line_str.split()
                    if words and words[-1].isdigit():
                        listed_page = int(words[-1])
                        topic = " ".join(words[:-1]).strip(". ")
                        actual_pdf_page = listed_page + INDEX_TO_PDF_PAGE_OFFSET
                        if 1 <= actual_pdf_page <= total:
                            index_entries.append({
                                "topic": topic,
                                "listed_page": listed_page,
                                "actual_pdf_page": actual_pdf_page,
                                "page_index": actual_pdf_page - 1
                            })

    return index_entries


# ==========================================#
# 4. TOC INDEX & OUTLINE EXTRACTOR#
# ==========================================

# Medical/Emergency domain stopwords to ignore when matching topics
STOPWORDS = {
    "accidentally", "spilled", "feeling", "suddenly", "getting", "strange", "trying",
    "really", "having", "please", "help", "very", "super", "like", "with", "from",
    "into", "some", "that", "this", "they", "them", "their", "there", "where", "when"
}

def get_target_pages_for_keywords(
    input_path: str,
    keywords: List[str]
) -> List[Dict]:
    """Finds target physical PDF pages matching emergency keywords from index + outlines with relevance ranking."""
    parsed_index = parse_index_pages(input_path)
    ignored_indices = parse_page_ranges(IGNORE_PAGE_RANGES)
    
    # Filter out generic stop words
    clean_kws = [k.lower() for k in keywords if len(k) > 3 and k.lower() not in STOPWORDS]
    if not clean_kws:
        clean_kws = [k.lower() for k in keywords if len(k) > 2]

    matched_scored = []
    seen_pages = set()

    # Match against parsed index (pages 3-10)
    for entry in parsed_index:
        topic_lower = entry["topic"].lower()
        score = 0
        for kw in clean_kws:
            if kw in topic_lower:
                # Exact word bonus
                if f" {kw} " in f" {topic_lower} ":
                    score += 10
                else:
                    score += 5
        
        if score > 0:
            p_idx = entry["page_index"]
            if p_idx not in ignored_indices and p_idx not in seen_pages:
                seen_pages.add(p_idx)
                entry_copy = dict(entry)
                entry_copy["relevance_score"] = score
                matched_scored.append(entry_copy)

    # Sort matches by highest relevance score
    matched_scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    return matched_scored


# ==========================================#
# 5. TEXT EXTRACTION WITH PDFPLUMBER#
# ==========================================

def extract_content_from_target_pages(input_path: str, matched_entries: List[Dict]) -> List[Dict]:
    """Extracts raw text, headings, and context from physical PDF pages."""
    results = []
    with pdfplumber.open(input_path) as pdf:
        total = len(pdf.pages)
        for entry in matched_entries:
            p_idx = entry["page_index"]
            if p_idx >= total:
                continue
            
            page = pdf.pages[p_idx]
            text = page.extract_text() or ""
            
            # Read follow-up page if topic continues
            if p_idx + 1 < total and p_idx + 1 not in parse_page_ranges(IGNORE_PAGE_RANGES):
                next_page_text = pdf.pages[p_idx + 1].extract_text() or ""
                if len(next_page_text) > 100:
                    text += "\n\n" + next_page_text[:1200]
            
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            heading = entry.get("topic") or (lines[0] if lines else "First Aid Guide")

            results.append({
                "condition": entry.get("topic", "Emergency First Aid"),
                "heading": heading,
                "pdf_page": entry.get("actual_pdf_page", p_idx + 1),
                "text": text,
                "source_location": f"PDF Page {entry.get('actual_pdf_page', p_idx + 1)} (Index listed pg {entry.get('listed_page', 'N/A')})"
            })
            
    return results


# ==========================================#
# 6. NVIDIA NIM CLIENT (Nemotron-3.5 & GLM-5.3)#
# ==========================================

class NVIDIANimClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("NVIDIA_NIM_API_KEY")
        if not self.api_key:
            raise ValueError("NVIDIA_NIM_API_KEY not found in environment/.env")
        
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=self.api_key
        )

    def generate_first_aid(
        self,
        condition: str,
        heading: str,
        raw_text: str,
        source_location: str,
        model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    ) -> dict:
        system_prompt = (
            "You are an expert Red Cross certified emergency medical responder. "
            "Translate the provided raw manual text into a structured JSON first-aid guide. "
            "Output JSON ONLY with keys: 'condition', 'emergency_severity', 'simple_summary', 'action_steps' (list of strings), 'what_to_avoid' (list of strings)."
        )

        user_content = (
            f"Condition: {condition}\n"
            f"Heading: {heading}\n"
            f"Source Location: {source_location}\n\n"
            f"Medical Manual Text:\n{raw_text[:3500]}"
        )

        # Try Nemotron / GLM-5.3
        try:
            comp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                max_tokens=2048,
            )
            content = comp.choices[0].message.content or ""
            
            # Extract JSON substring if formatted with markdown
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(content)
        except Exception as primary_err:
            # Fallback to z-ai/glm-5.3-flash
            fallback_model = "z-ai/glm-5.3-flash" if model != "z-ai/glm-5.3-flash" else "nvidia/nemotron-3.5-lightning-30b-a3b"
            comp = self.client.chat.completions.create(
                model=fallback_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.3,
                max_tokens=2048,
            )
            content = comp.choices[0].message.content or ""
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(content)


# ==========================================#
# 7. MAIN RUNNER#
# ==========================================

def run_first_aid_extraction(
    file_name: str = "redcross.pdf",
    conditions: List[str] = None
):
    if conditions is None:
        conditions = ["choking", "burn", "bleeding", "cpr", "fracture", "shock", "heart attack", "poison"]

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    input_path = os.path.join(backend_dir, "inputs", file_name)
    output_dir = os.path.join(backend_dir, "outputs")
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_path):
        print(f"[ERROR] PDF not found at {input_path}")
        return

    print(f"[1/4] Reading Index (Pages 3-10) with offset +2 from: {input_path}")
    matched_entries = get_target_pages_for_keywords(input_path, conditions)
    print(f"[2/4] Found {len(matched_entries)} matching sections for: {conditions}")
    for m in matched_entries[:8]:
        print(f"  * {m['topic']} -> Listed Page: {m['listed_page']} -> Target PDF Page: {m['actual_pdf_page']}")

    print(f"[3/4] Extracting text with pdfplumber...")
    extracted_docs = extract_content_from_target_pages(input_path, matched_entries)
    print(f"  Extracted content from {len(extracted_docs)} target sections")

    print(f"[4/4] Generating simplified First-Aid Guides via NVIDIA NIM (Nemotron-3.5 / GLM-5.3)...")
    client = NVIDIANimClient()
    guides = []

    for doc in extracted_docs[:4]:
        print(f"  -> Processing '{doc['condition']}' from {doc['source_location']}...")
        try:
            guide_data = client.generate_first_aid(
                condition=doc["condition"],
                heading=doc["heading"],
                raw_text=doc["text"],
                source_location=doc["source_location"],
                model="nvidia/nemotron-3.5-lightning-30b-a3b"
            )
            guide_data["source_location"] = doc["source_location"]
            guides.append(guide_data)
            print(f"  [OK] Generated guide for '{doc['condition']}'")
        except Exception as e:
            print(f"  [WARN] Failed for {doc['condition']}: {e}")

    out_file = os.path.join(output_dir, f"{os.path.splitext(file_name)[0]}_first_aid_guides.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(guides, f, indent=2)
    print(f"\n[DONE] Saved {len(guides)} structured first aid guides to: {out_file}")


if __name__ == "__main__":
    run_first_aid_extraction()
