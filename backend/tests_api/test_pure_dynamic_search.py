import os
import sys
import math
import re
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, extract_content_from_target_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)
doc_count = len(index_entries)

# Build dynamic document frequencies across the index entries
doc_freqs = Counter()
tokenized_docs = []
for entry in index_entries:
    raw_tokens = re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower())
    token_set = set(raw_tokens)
    tokenized_docs.append((entry, token_set))
    for t in token_set:
        doc_freqs[t] += 1

def pure_dynamic_search(query: str):
    # Dynamic tokenization without pre-determined stop words
    query_tokens = re.findall(r'\b[a-z]{3,}\b', query.lower())
    
    scored = []
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        
        for qt in query_tokens:
            for dt in doc_tokens:
                match_type = None
                if qt == dt:
                    match_type = "exact"
                elif len(qt) >= 4 and len(dt) >= 4 and (qt.startswith(dt) or dt.startswith(qt) or qt[:4] == dt[:4]):
                    match_type = "root"
                
                if match_type:
                    df = doc_freqs.get(dt, 1)
                    # Shannon Information Content / Dynamic IDF
                    # Common cross-cutting words (high df) automatically scale down to ~0
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    
                    # Dynamically penalize ubiquitous structural words without hardcoding
                    # If a word occurs in more than 3.5% of index entries, scale down exponentially
                    frequency_ratio = df / doc_count
                    if frequency_ratio > 0.035:
                        idf *= math.exp(-30.0 * frequency_ratio)
                    
                    weight = 3.5 if match_type == "exact" else 1.8
                    score += idf * weight
                    
        if score > 0.5:
            e = dict(entry)
            e["score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

queries = [
    ("Burns Case", "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."),
    ("Choking Case", "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."),
    ("Bleeding Case", "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately.")
]

for name, q in queries:
    print("\n" + "=" * 80)
    print(f"[{name}] User Query: \"{q}\"")
    matches = pure_dynamic_search(q)
    print("Top 3 Dynamically Ranked Topics (Pure Dynamic Corpus Weighting):")
    for m in matches[:3]:
        print(f"  -> '{m['topic']}' | Listed Pg: {m['listed_page']} -> PDF Pg: {m['actual_pdf_page']} (IDF Score: {m['score']})")
    
    if matches:
        extracted = extract_content_from_target_pages(PDF_PATH, matches[:1])
        text_snippet = extracted[0]['text'][:300].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\nStep 4 Extracted Excerpt ({extracted[0]['source_location']}):")
        print(f"Heading: {extracted[0]['heading']}")
        print(f"Excerpt: \"{text_snippet}...\"")
