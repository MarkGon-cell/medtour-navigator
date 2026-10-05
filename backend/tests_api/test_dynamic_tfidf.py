import os
import sys
import math
import re
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.api.first_aid_extractor import parse_index_pages, extract_content_from_target_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))
index_entries = parse_index_pages(PDF_PATH)

# Compute Document Frequency (DF) purely dynamically across the 371 index entries
doc_count = len(index_entries)
doc_freqs = Counter()

tokenized_docs = []
for entry in index_entries:
    tokens = set(re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower()))
    tokenized_docs.append((entry, tokens))
    for t in tokens:
        doc_freqs[t] += 1

# Pure dynamic TF-IDF BM25 scoring (No hardcoded or predetermined stop words)
def dynamic_search(query: str):
    query_tokens = re.findall(r'\b[a-z]{3,}\b', query.lower())
    
    # Also include sub-word matching (e.g. "burning" -> matches "burn", "choking" -> matches "chok")
    scored = []
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        topic_text = entry["topic"].lower()
        
        for qt in query_tokens:
            for dt in doc_tokens:
                # Exact token match or root/stem overlap
                if qt == dt or (len(qt) > 4 and len(dt) > 4 and (qt.startswith(dt[:4]) or dt.startswith(qt[:4]))):
                    # Pure dynamic IDF: log((N - n + 0.5) / (n + 0.5) + 1)
                    df = doc_freqs.get(dt, 1)
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    
                    # Exact match gets full weight, root match gets proportional weight
                    weight = 2.0 if qt == dt else 1.2
                    score += idf * weight
                    
                    # Extra priority for actionable procedural sections in manual ("What do I do", "Care of", "First aid")
                    if any(proc in topic_text for proc in ["what do i do", "care of", "first aid", "treatment"]):
                        score += 0.5 * idf

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
    matches = dynamic_search(q)
    print(f"Top 3 Matched Red Cross Topics (Pure Dynamic TF-IDF Scoring):")
    for m in matches[:3]:
        print(f"  -> '{m['topic']}' | Listed Pg: {m['listed_page']} -> PDF Pg: {m['actual_pdf_page']} (IDF Score: {m['dynamic_score']})")
    
    if matches:
        extracted = extract_content_from_target_pages(PDF_PATH, matches[:1])
        text_snippet = extracted[0]['text'][:300].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\nExtracted Step 4 Excerpt ({extracted[0]['source_location']}):")
        print(f"\"{text_snippet}...\"")
