import os
import sys
import math
import re
from collections import Counter
from typing import List, Dict, Any
import pdfplumber

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, parse_page_ranges, IGNORE_PAGE_RANGES

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)
doc_count = len(index_entries)

# Build Dynamic Document Frequency across the manual
doc_freqs = Counter()
tokenized_docs = []
ignored_pages = parse_page_ranges(IGNORE_PAGE_RANGES)

for entry in index_entries:
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower())
    token_set = set(raw_tokens)
    tokenized_docs.append((entry, token_set))
    for t in token_set:
        doc_freqs[t] += 1

def find_multi_chapter_sections(query: str, max_chapters: int = 3) -> List[Dict[str, Any]]:
    query_tokens = re.findall(r'\b[a-z]{3,}\b', query.lower())
    
    scored = []
    for entry, doc_tokens in tokenized_docs:
        # Ignore front-matter / prefaces
        if entry["page_index"] in ignored_pages or entry["listed_page"] < 18:
            continue
            
        topic_lower = entry["topic"].lower()
        score = 0.0
        
        for qt in query_tokens:
            for dt in doc_tokens:
                match_type = None
                if qt == dt:
                    match_type = "exact"
                elif len(qt) >= 4 and len(dt) >= 4:
                    # Root overlap (e.g. gash/wound, choking/choke, bleed/blood, burning/burn)
                    if qt.startswith(dt) or dt.startswith(qt) or qt[:4] == dt[:4]:
                        match_type = "root"
                        
                if match_type:
                    df = doc_freqs.get(dt, 1)
                    # Shannon Information Content / Dynamic BM25 IDF
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    
                    # Exponential dynamic downweighting of structural corpus terms
                    freq_ratio = df / doc_count
                    if freq_ratio > 0.03:
                        idf *= math.exp(-35.0 * freq_ratio)
                        
                    weight = 4.5 if match_type == "exact" else 2.5
                    if df <= 10:
                        weight *= 2.0
                        
                    score += idf * weight
                    
        # Give extra boost to procedural action sub-chapters ("What do I do", "Care of", "First aid for")
        if re.search(r'^[C-M]\.\d', entry["topic"]):
            score *= 1.35
        if any(act in topic_lower for act in ["what do i do", "care of", "first aid for", "when to refer"]):
            score *= 1.25

        if score > 0.5:
            e = dict(entry)
            e["dynamic_score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["dynamic_score"], reverse=True)
    
    # Diverse selection across distinct chapters & sub-chapters
    selected = []
    seen_chapters = set()
    for item in scored:
        # Extract main chapter group e.g. "H.3", "D.4", "C.5"
        m = re.match(r'^([A-Z](?:\.\d+)?)', item["topic"])
        chap_group = m.group(1) if m else item["topic"][:3]
        if chap_group not in seen_chapters or len(selected) < max_chapters:
            selected.append(item)
            seen_chapters.add(chap_group)
            if len(selected) >= max_chapters:
                break
                
    return selected

def extract_combined_manual_evidence(pdf_path: str, matched_sections: List[Dict[str, Any]]) -> str:
    combined_blocks = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        for section in matched_sections:
            p_idx = section["page_index"]
            if p_idx >= total:
                continue
            text = pdf.pages[p_idx].extract_text() or ""
            if p_idx + 1 < total and (p_idx + 1) not in ignored_pages:
                next_page = pdf.pages[p_idx + 1].extract_text() or ""
                if len(next_page) > 100:
                    text += "\n" + next_page[:800]
                    
            combined_blocks.append(
                f"--- [CHAPTER / SECTION: {section['topic']}] ---\n"
                f"(Source: Physical PDF Page {section['actual_pdf_page']}, Index Page {section['listed_page']})\n"
                f"{text.strip()[:1400]}\n"
            )
    return "\n\n".join(combined_blocks)

# Verify across the 3 test cases
queries = [
    ("Scald / Burn with Water", "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."),
    ("Airway / Choking / Throat", "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."),
    ("Bleeding & Deep Glass Cut", "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately.")
]

for name, q in queries:
    print("=" * 90)
    print(f">> CASE: {name} <<")
    print(f"User Complaint: \"{q}\"\n")
    
    sections = find_multi_chapter_sections(q, max_chapters=3)
    print(f"Matched {len(sections)} Related Chapters & Sub-Chapters:")
    for s in sections:
        print(f"  * [{s['topic']}] -> Physical PDF Page {s['actual_pdf_page']} (IDF Score: {s['dynamic_score']})")
        
    combined_text = extract_combined_manual_evidence(PDF_PATH, sections)
    print(f"\nCombined Multi-Chapter Excerpt Length: {len(combined_text)} characters")
    print("Preview of Evidence Block:")
    print(combined_text[:350].encode('ascii', 'ignore').decode('ascii') + "...\n")
