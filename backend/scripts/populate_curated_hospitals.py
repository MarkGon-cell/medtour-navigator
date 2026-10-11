"""
Curated Hospitals Enrichment Runner:
Accepts a list of hospital names & locations, queries Google AI Mode (via MCP or Web search),
and updates curated_hospitals with the structured columns:
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

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database.database import SessionLocal
from app.models.curated_hospital import CuratedHospital
from app.services.hospital_structurer import extract_batch_structured_hospitals

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("curated_populator")


def query_google_ai_mcp(query: str, timeout: int = 30) -> Optional[str]:
    """
    Spawns PleasePrompto/google-ai-mode-mcp over stdio, requests AI search, and collects the response.
    """
    cmd = ["cmd.exe", "/c", "npx", "-y", "google-ai-mode-mcp@latest"]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # 1. Initialize MCP
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "medtour-ai-populator", "version": "1.0"}
            }
        }) + "\n"
        proc.stdin.write(init_req)
        proc.stdin.flush()

        time.sleep(2.0)

        # 2. Call search_ai tool
        call_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_ai",
                "arguments": {"query": query}
            }
        }) + "\n"
        proc.stdin.write(call_req)
        proc.stdin.flush()

        # Send init and tool call together
        requests_payload = init_req + call_req
        stdout_data, _ = proc.communicate(input=requests_payload, timeout=timeout)
        for line in stdout_data.splitlines():
            try:
                data = json.loads(line.strip())
                if data.get("id") == 2:
                    content_list = data.get("result", {}).get("content", [])
                    if content_list and content_list[0].get("text"):
                        inner = json.loads(content_list[0]["text"])
                        return inner.get("markdown")
            except Exception:
                continue
    except subprocess.TimeoutExpired:
        logger.warning(f"Google AI Mode MCP timed out after {timeout}s")
        try:
            proc.kill()
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Google AI Mode MCP query error: {e}")

    return None


def query_gemini_search_fallback(query: str, timeout: int = 25) -> Optional[str]:
    """
    Fallback web search using gemini-search-mcp engine (Google AI Mode search).
    """
    try:
        mcp_path = r"C:\Users\ralph\.gemini\antigravity-ide\mcp\gemini-search-mcp"
        if mcp_path not in sys.path:
            sys.path.insert(0, mcp_path)
        from gemini_search.engine import AIModeEngine
        import asyncio

        async def _run():
            engine = AIModeEngine()
            try:
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
        logger.warning(f"gemini-search-mcp fallback error: {e}")
        return None


def fetch_hospital_grounding(hospital_names: List[str], location: str) -> str:
    """
    Tries Google AI Mode MCP first; if it fails or times out, uses gemini-search-mcp as fallback.
    """
    query = f"Hospitals in {location}: {', '.join(hospital_names)} contact numbers, emergency phone, website, specialties, rating, services"
    logger.info(f"Searching web grounding for: {query[:80]}...")
    
    # 1. Primary: google-ai-mode-mcp
    res = query_google_ai_mcp(query, timeout=20)
    if res and len(res.strip()) > 30:
        logger.info("✓ Grounding retrieved from google-ai-mode-mcp")
        return res

    # 2. Fallback: gemini-search-mcp
    logger.info("Attempting fallback via gemini-search-mcp...")
    fallback_res = query_gemini_search_fallback(query, timeout=20)
    if fallback_res and len(fallback_res.strip()) > 30:
        logger.info("✓ Grounding retrieved from gemini-search-mcp")
        return fallback_res

    logger.info("Continuing with direct AI structuring LLM knowledge.")
    return ""



def populate_curated_hospitals(limit: int = 5):
    """
    Fetches records from curated_hospitals needing real data,
    processes them in batch with Google AI Mode grounding and structured JSON generation,
    and updates phone, emergency_phone, website, emergency_available, speciality, tier, rating, services, amenities.
    """
    db = SessionLocal()
    try:
        targets: List[CuratedHospital] = (
            db.query(CuratedHospital)
            .filter(
                (CuratedHospital.ai_enriched == False) |
                (CuratedHospital.phone.is_(None)) |
                (CuratedHospital.speciality.is_(None))
            )
            .order_by(CuratedHospital.id.asc())
            .limit(limit)
            .all()
        )

        logger.info(f"Loaded {len(targets)} hospital(s) to populate with AI...")
        if not targets:
            return

        batch_input = [
            {
                "name": h.name,
                "location": f"{h.city}, {h.state}" if h.city else h.state
            }
            for h in targets
        ]

        # Acquire grounding context via Google AI Mode or gemini-search-mcp fallback
        h_names = [h.name for h in targets[:3]]
        loc_str = targets[0].city or targets[0].state or "India"
        grounding_text = fetch_hospital_grounding(h_names, loc_str)

        logger.info(f"Submitting batch to AI structuring engine for {len(batch_input)} facilities...")
        structured_results = extract_batch_structured_hospitals(batch_input, context_text=grounding_text)

        res_map = {item.get("name", "").strip().lower(): item for item in structured_results if item.get("name")}

        for h in targets:
            item = res_map.get(h.name.strip().lower())
            if not item:
                # Try finding closest match
                for k, v in res_map.items():
                    if k in h.name.lower() or h.name.lower() in k:
                        item = v
                        break

            if item:
                logger.info(f"\n=======================================================")
                logger.info(f"Populating DB row for: {h.name}")
                logger.info(f"Data: {json.dumps(item, indent=2)}")

                if item.get("phone"):
                    h.phone = str(item["phone"])
                if item.get("emergency_phone"):
                    h.emergency_phone = str(item["emergency_phone"])
                if item.get("website"):
                    h.website = str(item["website"])
                if item.get("emergency_available") is not None:
                    h.emergency_available = bool(item["emergency_available"])
                if item.get("speciality"):
                    h.speciality = str(item["speciality"])
                if item.get("tier"):
                    h.tier = str(item["tier"])
                if item.get("rating") is not None:
                    try:
                        h.rating = float(item["rating"])
                    except (ValueError, TypeError):
                        pass
                if item.get("services"):
                    h.services = str(item["services"])
                if item.get("amenities"):
                    h.amenities = str(item["amenities"])

                h.ai_enriched = True
                h.ai_summary = json.dumps(item)

                db.add(h)
                db.commit()
                logger.info(f"✓ Saved {h.name} in curated_hospitals!")

    finally:
        db.close()


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    populate_curated_hospitals(limit=count)

