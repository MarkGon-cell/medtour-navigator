import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.api.first_aid_extractor import parse_index_pages, extract_content_from_target_pages

PDF_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inputs", "redcross.pdf"))

# 1. Parse all index topics from the PDF
index_entries = parse_index_pages(PDF_PATH)
print(f"Loaded {len(index_entries)} topics from Red Cross PDF Index (Pages 3-10).")

# 2. Test dynamic matching with n-grams and stemming/subwords
def dynamic_semantic_match(user_text: str):
    words = [w.strip(".,!?:;\"'()[]") for w in user_text.lower().split() if len(w) > 2]
    
    # Generate 1-word, 2-word, and 3-word combinations from user query
    ngrams = []
    for i in range(len(words)):
        ngrams.append(words[i])
        if i + 1 < len(words):
            ngrams.append(f"{words[i]} {words[i+1]}")
        if i + 2 < len(words):
            ngrams.append(f"{words[i]} {words[i+1]} {words[i+2]}")
            
    scored = []
    for entry in index_entries:
        topic_lower = entry["topic"].lower()
        score = 0
        
        # Exact ngram matching
        for ng in ngrams:
            if ng in topic_lower:
                # Longer match phrases carry significantly higher weight
                score += len(ng.split()) * 15
                
        # Action/Emergency words in manual topic (Care, First Aid, What do I do) get extra relevance
        if "what do i do" in topic_lower or "first aid" in topic_lower or "care of" in topic_lower or "scald" in topic_lower or "burn" in topic_lower:
            score += 5
            
        if score > 0:
            e = dict(entry)
            e["score"] = score
            scored.append(e)
            
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored

queries = [
    "I accidentally spilled hot boiling tea on my forearm, the skin is bright red, burning like fire, and watery bubbles are popping up.",
    "My uncle was eating mutton and suddenly grabbed his throat, he can't talk, can't cough, and his face is turning slightly blue.",
    "Stepped on a large piece of broken window glass, deep gash on the leg, bright red blood is gushing out rapidly and tissues are soaked immediately."
]

for q in queries:
    print("\n" + "=" * 80)
    print(f"QUERY: \"{q}\"")
    matches = dynamic_semantic_match(q)
    print(f"Top Matched Red Cross Topics:")
    for m in matches[:4]:
        print(f"  -> Topic: '{m['topic']}' | Listed Pg {m['listed_page']} -> PDF Pg {m['actual_pdf_page']} (Score: {m['score']})")
    
    if matches:
        extracted = extract_content_from_target_pages(PDF_PATH, matches[:1])
        text_snippet = extracted[0]['text'][:300].replace('\n', ' ').encode('ascii', 'ignore').decode('ascii')
        print(f"\nExtracted Content ({extracted[0]['source_location']}):")
        print(f"\"{text_snippet}...\"")
