"""
Batch & targeted enrichment script for curated_hospitals using:
1) PleasePrompto/google-ai-mode-mcp (running via stdio subprocess)
2) Python AI enrichment extractor to update curated_hospitals table:
   - phone, emergency_phone, website, emergency_available
   - speciality, tier, rating, services, amenities
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import psycopg2
from psycopg2.extras import RealDictCursor

from app.database.database import SessionLocal
from app.models.curated_hospital import CuratedHospital
from app.services.hospital_ai_enricher import enrich_curated_hospital_from_ai

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mcp_enricher")


def run_google_ai_mcp_query(query: str, timeout: int = 30) -> Optional[str]:
    """
    Executes a query through PleasePrompto/google-ai-mode-mcp using MCP protocol over stdio.
    Returns the markdown output if successful.
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

        # 1. Send MCP initialize
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "medtour-enricher", "version": "1.0"}
            }
        }) + "\n"
        proc.stdin.write(init_req)
        proc.stdin.flush()

        time.sleep(1.8)

        # 2. Send call tool search_ai
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

        # 3. Read output lines until response id 2
        start_time = time.time()
        while time.time() - start_time < timeout:
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            
            try:
                data = json.loads(line.strip())
                if data.get("id") == 2:
                    content_list = data.get("result", {}).get("content", [])
                    if content_list and content_list[0].get("text"):
                        inner = json.loads(content_list[0]["text"])
                        proc.terminate()
                        return inner.get("markdown")
            except Exception:
                continue

        proc.terminate()
    except Exception as e:
        logger.error(f"Error querying Google AI MCP: {e}")
    
    return None


def enrich_hospitals_batch(limit: int = 5):
    """
    Finds hospitals with missing data in curated_hospitals and populates them using Google AI Mode MCP.
    """
    db = SessionLocal()
    try:
        hospitals = (
            db.query(CuratedHospital)
            .filter(
                (CuratedHospital.ai_enriched == False) |
                (CuratedHospital.phone.is_(None)) |
                (CuratedHospital.website.is_(None)) |
                (CuratedHospital.speciality.is_(None))
            )
            .order_by(CuratedHospital.id.asc())
            .limit(limit)
            .all()
        )

        logger.info(f"Found {len(hospitals)} hospitals to enrich.")

        for h in hospitals:
            location_str = f"{h.city}, {h.state}" if h.city else h.state
            query = f"{h.name} {location_str} hospital contact phone emergency website specialties rating"
            logger.info(f"Querying Google AI Mode for: {query}")
            
            ai_markdown = run_google_ai_mcp_query(query)
            if ai_markdown:
                logger.info(f"Received Google AI response ({len(ai_markdown)} chars). Enriching DB record...")
                enrich_curated_hospital_from_ai(db, h, ai_markdown)
                logger.info(
                    f"Updated {h.name} -> Phone: {h.phone}, Emer: {h.emergency_phone}, "
                    f"Web: {h.website}, Tier: {h.tier}, Spec: {h.speciality[:30] if h.speciality else None}"
                )
            else:
                logger.warning(f"No answer received from Google AI Mode for {h.name}")
            
            time.sleep(2)
    finally:
        db.close()


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    enrich_hospitals_batch(limit=count)
