import os
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure backend root is in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.api.first_aid_extractor import parse_index_pages, get_target_pages_for_keywords, extract_content_from_target_pages

def test_pdf_toc_and_extraction():
    print("\n--- Testing PDF Index (Pages 3-10, Offset +2) & Extractor ---")
    pdf_path = os.path.join(backend_dir, "inputs", "redcross.pdf")
    if not os.path.exists(pdf_path):
        print(f"[WARN] Test PDF not found at {pdf_path}")
        return

    # 1. Test Index extraction (pages 3-10)
    index_entries = parse_index_pages(pdf_path)
    print(f"[OK] Extracted {len(index_entries)} index entries from pages 3-10")
    for item in index_entries[:5]:
        print(f"  * {item['topic']} (Listed pg: {item['listed_page']} -> Target PDF page: {item['actual_pdf_page']})")
    
    # 2. Test keyword matching
    keywords = ["choking", "burn", "bleeding", "cpr", "fracture"]
    matched = get_target_pages_for_keywords(pdf_path, keywords)
    print(f"[OK] Matched keywords {keywords} to {len(matched)} target sections")
    for m in matched[:5]:
        print(f"  * {m['topic']} -> Target PDF Page: {m['actual_pdf_page']}")
    
    # 3. Test text extraction with pdfplumber
    if matched:
        sample = matched[:2]
        extracted = extract_content_from_target_pages(pdf_path, sample)
        print(f"[OK] Extracted text from {len(extracted)} sections")
        for item in extracted:
            print(f"  📖 Condition: '{item['condition']}' (PDF Page: {item['pdf_page']}, Text: {len(item['text'])} chars)")
            
    print("\n[SUCCESS] PDF Extractor test completed successfully!")

if __name__ == "__main__":
    test_pdf_toc_and_extraction()
