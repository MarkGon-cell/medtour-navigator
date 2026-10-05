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

# Build dynamic document frequencies across the manual
doc_freqs = Counter()
tokenized_docs = []
for entry in index_entries:
    tokens = set(re.findall(r'\b[a-z]{3,}\b', entry["topic"].lower()))
    tokenized_docs.append((entry, tokens))
    for t in tokens:
        doc_freqs[t] += 1

def dynamic_search_v3(query: str):
    query_tokens = re.findall(r'\b[a-z]{3,}\b', query.lower())
    scored = []
    
    for entry, doc_tokens in tokenized_docs:
        score = 0.0
        topic_text = entry["topic"].lower()
        
        # Calculate dynamic query length normalization
        for qt in query_tokens:
            for dt in doc_tokens:
                match = False
                weight = 1.0
                if qt == dt:
                    match = True
                    weight = 3.0
                elif len(qt) >= 4 and len(dt) >= 4:
                    if qt.startswith(dt) or dt.startswith(qt) or qt[:4] == dt[:4]:
                        match = True
                        weight = 2.0
                
                if match:
                    df = doc_freqs.get(dt, 1)
                    # Dynamic IDF (High for specific medical terms, low for ubiquitous words)
                    idf = math.log((doc_count - df + 0.5) / (df + 0.5) + 1.0)
                    
                    # If the word appears in more than 10% of topics, penalize its weight dynamically
                    if df > (doc_count * 0.05):
                        weight *= 0.2
                    
                    score += idf * weight
                    
        # Give higher weight to clinical condition chapters (H.3 Burns, C.5 Choking, D.4 Bleeding, E.4 Fractures)
        if re.search(r'^[A-Z]\.\d', entry["topic"]):
            score *= 1.25

        if score > 0:
            e = dict(entry)
            e["score"] = round(score, 2)
            scored.append(e)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

queries = [
    ("Burns", "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up."),
    ("Choking", "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue."),
    ("Bleeding", "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately.")
]

for name, q in queries:
    print("\n" + "=" * 80)
    print(f"[{name}] QUERY: \"{q}\"")
    matches = dynamic_search_v3(q)
    print("Top 3 Dynamically Matched Red Cross Topics:")
    for m in matches[:3]:
        print(f"  -> '{m['topic']}' | Listed Pg: {m['listed_page']} -> PDF Pg: {m['actual_pdf_page']} (Score: {m['score']})")
    
    if matches:
        extracted = extract_content_from_target_pages(PDF_PATH, matches[:1])
        text_snippet = extracted[0]['text'][:300].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\nStep 4 Extracted Excerpt ({extracted[0]['source_location']}):")
        print(f"\"{text_snippet}...\"")
