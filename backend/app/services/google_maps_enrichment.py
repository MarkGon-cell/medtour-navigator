"""
Module 4: Google Places / Maps Detailed Contact & Operational Enrichment
Enriches the 7 chosen hospitals with:
- emergency_services, emergency_phone, ambulance_phone, bloodbank_phone
- phone, mobile, tollfree, helpline, website, email
- opening_hours, rating, review_count
Populates the database with these fields if available.
"""
import os
import logging
import requests
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.hospital import Hospital

logger = logging.getLogger(__name__)

GOOGLE_PLACES_KEY = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_MAPS_DEMO_API_KEY")

def fetch_google_place_details(place_id: str) -> Dict[str, Any]:
    """
    Calls Google Places API (New) Place Details for full phone, website, hours, rating.
    """
    if not GOOGLE_PLACES_KEY or not place_id:
        return {}

    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": "id,internationalPhoneNumber,nationalPhoneNumber,websiteUri,regularOpeningHours,rating,userRatingCount,formattedAddress"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug(f"Place Details fetch failed: {e}")
    return {}

def enrich_hospitals_from_google_maps(
    db: Session,
    hospitals: List[Dict[str, Any]],
    latitude: float,
    longitude: float
) -> List[Dict[str, Any]]:
    """
    Finds and enriches the chosen hospitals with Google Maps contact, website,
    opening hours, user star ratings, and review counts.
    Populates Postgres DB for permanent storage.
    """
    if not GOOGLE_PLACES_KEY or not hospitals:
        return hospitals

    # 1. Fetch nearby places matching these hospitals
    search_url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.internationalPhoneNumber,places.nationalPhoneNumber,places.websiteUri,places.regularOpeningHours"
    }
    payload = {
        "includedTypes": ["hospital", "doctor"],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": 15000.0,
            }
        },
        "maxResultCount": 20,
    }

    places_by_name = {}
    try:
        resp = requests.post(search_url, headers=headers, json=payload, timeout=6.0)
        if resp.status_code == 200:
            data = resp.json()
            for p in data.get("places", []):
                d_name = (p.get("displayName") or {}).get("text", "").lower().strip()
                if d_name:
                    places_by_name[d_name] = p
    except Exception as e:
        logger.debug(f"Google Places Search Nearby failed: {e}")

    # 2. Match each of the chosen 7 hospitals
    for h in hospitals:
        h_name = (h.get("name") or "").lower().strip()
        matched_place = None
        for p_name, place in places_by_name.items():
            if h_name in p_name or p_name in h_name:
                matched_place = place
                break

        if matched_place:
            phone = matched_place.get("nationalPhoneNumber") or matched_place.get("internationalPhoneNumber")
            website = matched_place.get("websiteUri")
            rating = matched_place.get("rating")
            reviews = matched_place.get("userRatingCount")
            
            hours_obj = matched_place.get("regularOpeningHours") or {}
            hours_str = "24/7" if hours_obj.get("openNow") else None
            if hours_obj.get("weekdayDescriptions"):
                hours_str = "; ".join(hours_obj["weekdayDescriptions"][:2])

            if phone and not h.get("phone"):
                h["phone"] = phone
            if website and not h.get("website"):
                h["website"] = website
            if rating is not None:
                h["rating"] = float(rating)
            if reviews is not None:
                h["review_count"] = int(reviews)
            if hours_str:
                h["opening_hours"] = hours_str

            # Update Postgres DB
            h_id = h.get("id")
            if h_id and isinstance(h_id, int):
                try:
                    db_h = db.query(Hospital).filter(Hospital.id == h_id).first()
                    if db_h:
                        if phone and not db_h.phone:
                            db_h.phone = phone
                        if website and not db_h.website:
                            db_h.website = website
                        if rating is not None:
                            db_h.rating = float(rating)
                        if reviews is not None:
                            db_h.review_count = int(reviews)
                        if hours_str and not db_h.opening_hours:
                            db_h.opening_hours = hours_str
                        db.commit()
                except Exception as e:
                    db.rollback()
                    logger.debug(f"DB update error: {e}")

    return hospitals
