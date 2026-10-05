import os
import sys
import math
import re
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, extract_content_from_target_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

# Corpus frequency
doc_count = len(index_entries)
doc_freqs = Counter()
tokenized_docs = []

for entry in index_entries:
    # Extract alpha tokens
    tokens = set(re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower()))
    tokenized_docs.append((entry, tokens))
    for t in tokens:
        doc_freqs[t] += 1

# Mathematical Dynamic Information Weight:
# Words appearing on many pages across the manual have lower information value,
# words appearing rarely in specific sections (like 'bleeding', 'burn', 'choking', 'fracture') have high information value.
def dynamic_search_v2(query: str):
    query_tokens = re.findall(r'\b[a-z]{3,}\b', query.lower())
    
    scored = []
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        topic_text = entry["topic"].lower()
        
        for qt in query_tokens:
            for dt in doc_tokens:
                match_type = None
                if qt == dt:
                    match_type = "exact"
                elif len(qt) >= 4 and len(dt) >= 4:
                    if qt.startswith(dt) or dt.startswith(qt) or qt[:4] == dt[:4]:
                        match_type = "stem"
                
                if match_type:
                    df = doc_freqs.get(dt, 1)
                    # Information Content (Shannon entropy / IDF)
                    # Common cross-cutting words (df > 15) naturally scale down to ~0
                    idf = max(0.0, math.log((doc_count - df + 0.5) / (df + 0.5)))
                    
                    if idf > 1.2: # Only informative words contribute
                        weight = 3.0 if match_type == "exact" else 1.8
                        score += idf * weight
                        
                        # Extra bonus if it is a direct action procedure
                        if any(k in topic_text for k in ["what do i do", "care of", "first aid", "treatment", "wounds", "bleeding"]):
                            score += 1.5

        if score > 0:
            e = dict(entry)
            e["dynamic_score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["dynamic_score"], reverse=True)
    return scored

queries = [
    "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up.",
    "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
    "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
]

for q in queries:
    print("\n" + "=" * 80)
    print(f"QUERY: \"{q}\"")
    matches = dynamic_search_v2(q)
    print(f"Top 3 Matched Red Cross Topics (Dynamic Information Weighting):")
    for m in matches[:3]:
        print(f"  -> '{m['topic']}' | Listed Pg: {m['listed_page']} -> PDF Pg: {m['actual_pdf_page']} (IDF Score: {m['dynamic_score']})")
    
    if matches:
        extracted = extract_content_from_target_pages(PDF_PATH, matches[:1])
        text_snippet = extracted[0]['text'][:300].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\nExtracted Step 4 Excerpt ({extracted[0]['source_location']}):")
        print(f"\"{text_snippet}...\"")
