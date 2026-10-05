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

# 1. Build Pure Mathematical Term Frequency & Document Frequency
doc_freqs = Counter()
tokenized_docs = []
ignored_pages = parse_page_ranges(IGNORE_PAGE_RANGES)

for entry in index_entries:
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower())
    token_set = set(raw_tokens)
    tokenized_docs.append((entry, token_set))
    for t in token_set:
        doc_freqs[t] += 1

# 2. Multi-Chapter Dynamic Matcher
def multi_chapter_dynamic_search(user_query: str, max_chapters: int = 4) -> List[Dict[str, Any]]:
    query_tokens = re.findall(r'\b[a-z]{3,}\b', user_query.lower())
    
    scored_entries = []
    for entry, doc_tokens in tokenized_docs:
        # Skip preface/acknowledgements
        if entry["page_index"] in ignored_pages or entry["listed_page"] < 18:
            continue
            
        score = 0.0
        topic_lower = entry["topic"].lower()
        
        for qt in query_tokens:
            for dt in doc_tokens:
                match_type = None
                if qt == dt:
                    match_type = "exact"
                elif len(qt) >= 4 and len(dt) >= 4 and (qt.startswith(dt) or dt.startswith(qt) or qt[:4] == dt[:4]):
                    match_type = "root"
                    
                if match_type:
                    df = doc_freqs.get(dt, 1)
                    # Standard BM25 IDF
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    
                    # Dynamically downweight structural corpus words without hardcoding
                    freq_ratio = df / doc_count
                    if freq_ratio > 0.035:
                        idf *= math.exp(-30.0 * freq_ratio)
                        
                    weight = 4.0 if match_type == "exact" else 2.2
                    if df <= 10:
                        weight *= 2.0
                        
                    score += idf * weight
                    
        # Give strong boost to clinical emergency chapters (H: Burns, C: Respiratory/Choking, D: Bleeding/Circulation, E: Fractures)
        if re.search(r'^[C-M]\.\d', entry["topic"]):
            score *= 1.4

        if score > 0.5:
            e = dict(entry)
            e["dynamic_score"] = round(score, 2)
            scored_entries.append(e)

    scored_entries.sort(key=lambda x: x["dynamic_score"], reverse=True)
    
    # Select from distinct chapters/sub-sections so we aggregate wide context
    selected = []
    seen_prefixes = set()
    for item in scored_entries:
        # Extract chapter letter e.g., 'H', 'D', 'C', 'E'
        prefix = item["topic"][:3].strip()
        if prefix not in seen_prefixes or len(selected) < max_chapters:
            selected.append(item)
            seen_prefixes.add(prefix)
            if len(selected) >= max_chapters:
                break
                
    return selected


# 3. Multi-Chapter Excerpt Extractor
def extract_multi_chapter_excerpts(input_path: str, matched_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    with pdfplumber.open(input_path) as pdf:
        total = len(pdf.pages)
        for entry in matched_entries:
            p_idx = entry["page_index"]
            if p_idx >= total:
                continue
            text = pdf.pages[p_idx].extract_text() or ""
            # Include next follow-up page for procedure continuity
            if p_idx + 1 < total and (p_idx + 1) not in ignored_pages:
                next_text = pdf.pages[p_idx + 1].extract_text() or ""
                if len(next_text) > 100:
                    text += "\n" + next_text[:1000]
                    
            clean_lines = [l.strip() for l in text.split("\n") if l.strip()]
            heading = entry.get("topic") or (clean_lines[0] if clean_lines else "Chapter")
            
            results.append({
                "chapter_topic": entry.get("topic"),
                "pdf_page": entry.get("actual_pdf_page"),
                "source_ref": f"Red Cross Manual Physical Pg {entry.get('actual_pdf_page')} (TOC listed Pg {entry.get('listed_page')})",
                "text": text[:1500]
            })
    return results


# Test across multiple complex trauma cases
test_cases = [
    {
        "name": "Severe Scald / Burn with Blisters",
        "input": "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."
    },
    {
        "name": "Choking and Obstructed Breathing",
        "input": "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."
    },
    {
        "name": "Severe Bleeding & Deep Glass Laceration",
        "input": "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
    }
]

print("=" * 90)
print("TESTING MULTI-CHAPTER DYNAMIC SEARCH & COMBINED EXTRACTION")
print("=" * 90)

for case in test_cases:
    print(f"\n>> CASE: {case['name']} <<")
    print(f"User Input: \"{case['input']}\"")
    
    matches = multi_chapter_dynamic_search(case['input'], max_chapters=3)
    print(f"\n[Multi-Chapter Hits Matched in Index: {len(matches)}]")
    for m in matches:
        print(f"  * Chapter: '{m['topic']}' | Listed Pg {m['listed_page']} -> PDF Pg {m['actual_pdf_page']} (IDF Score: {m['dynamic_score']})")
        
    excerpts = extract_multi_chapter_excerpts(PDF_PATH, matches)
    print(f"\n[Combined Multi-Chapter Evidence Extracted: {len(excerpts)} sections]")
    for idx, ex in enumerate(excerpts, 1):
        clean_snip = ex['text'][:180].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"  [{idx}] Ref: {ex['source_ref']}")
        print(f"      Heading: {ex['chapter_topic']}")
        print(f"      Evidence: \"{clean_snip}...\"\n")
