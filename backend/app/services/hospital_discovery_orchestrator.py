"""
Master Workflow Orchestrator for Hospital Discovery & Symptom Matching.

Workflow:
1. Patient enters symptoms ("how ya feeling").
2. Retrieve initial candidate facilities within the requested GPS radius (Postgres + Overpass + Geoapify).
3. Apply Clinical Guardrails (Module 1) to eliminate mismatched single-specialty clinics.
4. Google AI Search Enrichment (Module 2):
   - Enriches specialties, facilities, misc_facilities, emergency_available, emergency_services.
   - Discovers any unlisted new hospitals within the radius with full schema fields.
   - Populates the database with verified information.
5. NVIDIA NIM Matching (Module 3):
   - Selects EXACTLY 7 hospitals that can properly treat what the patient feels.
   - Designates the top 2 as 'best' and 'nearest', and the remaining as 'nearby'.
6. Google Maps / Places Detailed Contact Enrichment (Module 4):
   - Enriches the 7 hospitals with emergency phone, reception phone, website, opening hours, star rating, reviews.
   - Populates the database.
7. Return authoritative structured results to the patient.
"""
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.services.triage_guardrail import filter_compatible_facilities
from app.services.ai_hospital_enrichment import enrich_or_discover_hospitals_with_ai
from app.services.hospital_nim_selector import select_and_tier_seven_hospitals
from app.services.google_maps_enrichment import enrich_hospitals_from_google_maps

logger = logging.getLogger(__name__)

def execute_hospital_discovery_workflow(
    db: Session,
    symptoms: str,
    target_specialty: str,
    urgency: str,
    raw_candidates: List[Dict[str, Any]],
    latitude: float,
    longitude: float,
    radius_km: float
) -> List[Dict[str, Any]]:
    """
    Executes the complete multi-stage hospital discovery and clinical recommendation pipeline.
    """
    logger.info(f"[Workflow] Starting discovery for symptoms: '{symptoms}' | Specialty: {target_specialty}")
    
    # Stage 1: Clinical Guardrails — Disqualify mismatched single-specialty clinics (e.g. eye care for food poisoning)
    compatible_candidates = filter_compatible_facilities(raw_candidates, symptoms, target_specialty)
    logger.info(f"[Workflow] After clinical guardrails: {len(compatible_candidates)} candidates remain.")

    # Stage 2: Google AI Search Enrichment & Missing Hospital Discovery (Populate DB)
    enriched_candidates = enrich_or_discover_hospitals_with_ai(
        db=db,
        existing_hospitals=compatible_candidates,
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km
    )
    logger.info(f"[Workflow] After AI enrichment & discovery: {len(enriched_candidates)} candidates.")

    # Stage 3: NVIDIA NIM 7-Hospital Selection (Best, Nearest, and up to 5 Nearby)
    selected_seven = select_and_tier_seven_hospitals(
        symptoms=symptoms,
        specialty=target_specialty,
        urgency=urgency,
        candidates=enriched_candidates
    )
    logger.info(f"[Workflow] Selected {len(selected_seven)} treatment facilities.")

    # Stage 4: Google Places / Maps Contact, Opening Hours, and Ratings Enrichment (Populate DB)
    final_seven = enrich_hospitals_from_google_maps(
        db=db,
        hospitals=selected_seven,
        latitude=latitude,
        longitude=longitude
    )
    logger.info(f"[Workflow] Completed full pipeline enrichment.")

    return final_seven
