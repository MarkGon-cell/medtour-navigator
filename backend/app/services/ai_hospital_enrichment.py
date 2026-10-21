"""
Module 2: Google AI Search & Structured Hospital Enrichment
Uses Google AI Search / Web AI knowledge to query:
- specialties, facilities, miscellaneous_facilities, emergency_available, emergency_services
- AND discovers unlisted new hospitals in the radius with schema attributes.
Populates the database with new/updated information.
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.hospital import Hospital
from app.services import google_ai_search
from app.api.hybrid_first_aid_retriever import nim_generate_json

logger = logging.getLogger(__name__)

def enrich_or_discover_hospitals_with_ai(
    db: Session,
    existing_hospitals: List[Dict[str, Any]],
    latitude: float,
    longitude: float,
    radius_km: float,
    area_hint: str = ""
) -> List[Dict[str, Any]]:
    """
    1. Asks AI for clinical infrastructure of existing hospitals in radius:
       specialties, facilities, miscellaneous_facilities, emergency_available, emergency_services.
    2. Queries for any NEW missing hospitals within this radius.
    3. Populates Postgres database with verified/enriched records.
    """
    api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    names_to_enrich = [h.get("name") for h in existing_hospitals[:8] if h.get("name")]
    
    system_prompt = (
        "You are an authoritative hospital infrastructure intelligence system in India.\n"
        "Your role is two-fold:\n"
        "1. For the given list of hospitals, provide accurate clinical details:\n"
        "   - specialties: Comma-separated specialties (e.g. Cardiology, Gastroenterology, General Medicine)\n"
        "   - facilities: Infrastructure (e.g. ICU, Blood Bank, CT Scan, Ultrasound, Dialysis, Operating Theatres)\n"
        "   - miscellaneous_facilities: Auxiliary support (e.g. 24/7 Pharmacy, Cashless Insurance, Oxygen)\n"
        "   - emergency_available: boolean true/false (has 24/7 casualty/trauma ward)\n"
        "   - emergency_services: Specific emergency capabilities\n\n"
        "2. If there are other prominent general or multispeciality hospitals in this immediate radius (~{radius_km}km) "
        "not mentioned in the list, provide them with:\n"
        "   - name, category, care_type, discipline, city, state, district, subdistrict, address, pincode, "
        "     latitude, longitude, specialties, facilities, miscellaneous_facilities, emergency_available, emergency_services.\n\n"
        "OUTPUT strictly valid JSON matching this schema:\n"
        "{\n"
        '  "enriched": [\n'
        '    {"name": "<exact name>", "specialties": "...", "facilities": "...", "miscellaneous_facilities": "...", "emergency_available": true, "emergency_services": "..."}\n'
        "  ],\n"
        '  "new_discovered": [\n'
        '    {\n'
        '      "name": "...", "category": "Hospital", "care_type": "Secondary", "discipline": "Allopathy",\n'
        '      "city": "...", "state": "...", "district": "...", "subdistrict": "...", "address": "...", "pincode": "...",\n'
        '      "latitude": 0.0, "longitude": 0.0, "specialties": "...", "facilities": "...", "miscellaneous_facilities": "...",\n'
        '      "emergency_available": true, "emergency_services": "..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    
    user_prompt = (
        f"Location Coordinates: Latitude {latitude}, Longitude {longitude} (Radius: {radius_km} km).\n"
        f"Area: {area_hint or 'Local Region'}\n"
        f"Existing Hospitals to Enrich:\n{json.dumps(names_to_enrich, ensure_ascii=False)}"
    )
    
    result = None
    if api_key:
        try:
            result = nim_generate_json(
                api_key=api_key,
                system_prompt=system_prompt,
                user_message=user_prompt,
                expect_key="enriched",
                per_model_timeout=6.0,
                max_retries=1
            )
        except Exception as e:
            logger.warning(f"AI enrichment request failed: {e}")
            
    if not result:
        return existing_hospitals

    enriched_map = {}
    for item in result.get("enriched", []):
        if isinstance(item, dict) and item.get("name"):
            enriched_map[item["name"].strip().lower()] = item

    # Update in DB and memory
    for h in existing_hospitals:
        name_key = (h.get("name") or "").strip().lower()
        if name_key in enriched_map:
            enrichment = enriched_map[name_key]
            h["specialties"] = enrichment.get("specialties") or h.get("specialties")
            h["facilities"] = enrichment.get("facilities") or h.get("facilities")
            h["miscellaneous_facilities"] = enrichment.get("miscellaneous_facilities") or h.get("miscellaneous_facilities")
            h["emergency_available"] = bool(enrichment.get("emergency_available", h.get("emergency_available")))
            h["emergency_services"] = enrichment.get("emergency_services") or h.get("emergency_services")
            
            # Persist to Postgres if ID exists
            h_id = h.get("id")
            if h_id and isinstance(h_id, int):
                try:
                    db_h = db.query(Hospital).filter(Hospital.id == h_id).first()
                    if db_h:
                        if not db_h.specialties:
                            db_h.specialties = h["specialties"]
                        if not db_h.facilities:
                            db_h.facilities = h["facilities"]
                        if not db_h.miscellaneous_facilities:
                            db_h.miscellaneous_facilities = h["miscellaneous_facilities"]
                        db_h.emergency_available = h["emergency_available"]
                        if not db_h.emergency_services:
                            db_h.emergency_services = h["emergency_services"]
                        db.commit()
                except Exception as e:
                    db.rollback()
                    logger.debug(f"DB update skipped: {e}")

    # Process newly discovered hospitals into DB and candidate list
    all_results = list(existing_hospitals)
    for new_h in result.get("new_discovered", []):
        if not isinstance(new_h, dict) or not new_h.get("name"):
            continue
        try:
            # Check if hospital already exists by name
            existing = db.query(Hospital).filter(Hospital.name.ilike(new_h["name"].strip())).first()
            if not existing:
                created = Hospital(
                    name=new_h["name"].strip(),
                    category=new_h.get("category", "Hospital"),
                    care_type=new_h.get("care_type", "Secondary"),
                    discipline=new_h.get("discipline", "Allopathy"),
                    city=new_h.get("city", ""),
                    state=new_h.get("state", "Maharashtra"),
                    district=new_h.get("district", ""),
                    subdistrict=new_h.get("subdistrict", ""),
                    address=new_h.get("address", ""),
                    pincode=new_h.get("pincode", ""),
                    latitude=float(new_h.get("latitude") or latitude),
                    longitude=float(new_h.get("longitude") or longitude),
                    specialties=new_h.get("specialties", ""),
                    facilities=new_h.get("facilities", ""),
                    miscellaneous_facilities=new_h.get("miscellaneous_facilities", ""),
                    emergency_available=bool(new_h.get("emergency_available", False)),
                    emergency_services=new_h.get("emergency_services", ""),
                    source="google_ai_discovery"
                )
                db.add(created)
                db.commit()
                db.refresh(created)
                
                # Add to return list
                all_results.append({
                    "id": created.id,
                    "name": created.name,
                    "address": created.address,
                    "city": created.city,
                    "state": created.state,
                    "latitude": created.latitude,
                    "longitude": created.longitude,
                    "specialties": created.specialties,
                    "facilities": created.facilities,
                    "emergency_available": created.emergency_available,
                    "source": "google_ai_discovery"
                })
        except Exception as e:
            db.rollback()
            logger.debug(f"Could not insert discovered hospital: {e}")

    return all_results
