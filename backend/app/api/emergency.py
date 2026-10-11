"""
Emergency endpoints.

SOS dispatch contract:
    Tapping SOS does two things at once on the client:
        1. opens tel:112 -- the real emergency channel, works with no network;
        2. POSTs /emergency/sos here, which curates WHERE the ambulance should
           go: it finds the nearest emergency-capable hospital from Postgres +
           Overpass + Geoapify, computes the route and ETA from the caller's
           GPS, and returns a dispatch packet (name, phone, address, distance,
           ETA, Google Maps route link).

    MedTour has no ambulance-partner API, so this is a dispatch *packet* for
    the nearest ER -- not a claim that a vehicle was paged. The 112 call is
    the actual emergency summoning; this endpoint tells the caller and their
    driver where to go.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import get_optional_current_user
from app.database.database import get_db
from app.models.hospital import Hospital
from app.models.user import User
from app.services import discovery
from app.services.geo import haversine_km

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emergency", tags=["Emergency"])

# Headline numbers, surfaced so the client can render them and keep working
# offline. The current client hardcodes these too, for offline reliability.
EMERGENCY_NUMBERS = {
    "national_emergency": "112",
    "ambulance": "108",
    "police": "100",
    "fire": "101",
}

# Average urban ambulance speed used for the ETA estimate (km/h). City traffic
# with signal priority assumed; a coarse estimate, not a routing engine.
_AVG_AMBULANCE_SPEED_KMH = 35.0
# Search radius for the nearest emergency-capable hospital on the SOS path.
_SOS_RADIUS_KM = 25.0
# Straight-line distance is shorter than road distance; pad ETA accordingly.
_ROUTE_PADDING = 1.3


class SOSRequest(BaseModel):
    latitude: float
    longitude: float
    address: str
    pincode: Optional[str] = None
    message: Optional[str] = None
    contact_emergency_services: bool = True


def _estimate_eta_minutes(distance_km: float) -> int:
    road_km = distance_km * _ROUTE_PADDING
    minutes = (road_km / _AVG_AMBULANCE_SPEED_KMH) * 60.0
    # Never show less than a minute; cap runaway estimates.
    return max(1, min(int(round(minutes)), 90))


def _find_nearest_emergency_hospital(
    db: Session,
    latitude: float,
    longitude: float,
) -> Optional[dict]:
    """
    Nearest emergency-capable hospital from Postgres + Overpass + Geoapify.

    Returns a dict with the hospital's contact block, distance and ETA, or
    None when nothing emergency-capable is found within _SOS_RADIUS_KM.
    Never raises -- a dead provider must not block the SOS acknowledgement.
    """
    candidates: list[dict] = []

    def _is_general_or_multispeciality(name: str, specialties: str = "", category: str = "") -> bool:
        text = f"{name} {specialties} {category}".lower()
        positive = [
            "multi", "general", "civil hospital", "district hospital",
            "tertiary", "trauma", "casualty", "government hospital",
            "govt hospital", "medical college", "acute care", "critical care",
            "emergency care", "mission hospital", "community health centre", "chc"
        ]
        return any(k in text for k in positive)

    def _is_disqualified_clinic(name: str, specialties: str = "", category: str = "") -> bool:
        text = f"{name} {specialties} {category}".lower()
        if any(k in text for k in ["multi", "general", "civil", "district", "trauma", "medical college"]):
            return False
        disqualifiers = [
            "eye", "ophthal", "dental", "dentist", "skin", "derma", "cosmetic",
            "urology", "physio", "ayurved", "homeo", "fertility", "ivf",
            "day care", "outpatient clinic", "dispensary"
        ]
        return any(k in text for k in disqualifiers)

    def _consider(name, lat, lon, phone, address, city, emergency, specialties="", category=""):
        if not emergency:
            return
        if _is_disqualified_clinic(name or "", specialties or "", category or ""):
            return
        dist = haversine_km(latitude, longitude, lat, lon)
        if dist > _SOS_RADIUS_KM:
            return

        is_gen_multi = _is_general_or_multispeciality(name or "", specialties or "", category or "")
        candidates.append({
            "name": name,
            "address": address,
            "city": city,
            "phone": phone,
            "latitude": lat,
            "longitude": lon,
            "distance_km": round(dist, 2),
            "eta_minutes": _estimate_eta_minutes(dist),
            "is_general_or_multispeciality": is_gen_multi,
            "google_maps_route": (
                f"https://www.google.com/maps/dir/?api=1"
                f"&origin={latitude},{longitude}&destination={lat},{lon}"
                f"&travelmode=driving"
            ),
        })

    # --- Source 1: local Postgres directory (bbox pre-filter).
    try:
        min_lat, max_lat, min_lon, max_lon = discovery.bounding_box(
            latitude, longitude, _SOS_RADIUS_KM
        )
        local_rows = (
            db.query(Hospital)
            .filter(
                Hospital.latitude >= min_lat,
                Hospital.latitude <= max_lat,
                Hospital.longitude >= min_lon,
                Hospital.longitude <= max_lon,
            )
            .all()
        )
        for h in local_rows:
            if h.latitude and h.longitude:
                _consider(
                    h.name, h.latitude, h.longitude, h.phone,
                    h.address, h.city, h.emergency_available,
                    specialties=h.specialties or "",
                    category=h.category or "",
                )
    except Exception as e:
        logger.warning("SOS Postgres lookup failed: %s", e)

    # --- Sources 2 & 3: Overpass + Geoapify (cached by discovery). persist=False
    #     keeps the urgent SOS path read-only; fast=True bounds a dead Overpass
    #     to seconds so dispatch can never hang on flaky mirrors.
    try:
        merged = discovery.discover(
            db, latitude, longitude, _SOS_RADIUS_KM,
            persist=False, limit=discovery.MAX_RESULTS, fast=True,
        )
        for row in merged.get("results", []):
            lat, lon = row.get("latitude"), row.get("longitude")
            if lat is None or lon is None:
                continue
            _consider(
                row.get("name"), lat, lon, row.get("phone"),
                row.get("address"), row.get("city"),
                row.get("emergency_available"),
                specialties=row.get("specialties") or "",
                category=row.get("category") or "",
            )
    except Exception as e:
        logger.warning("SOS Overpass/Geoapify discovery failed: %s", e)

    if not candidates:
        return None

    # Sort candidates prioritizing General / Multi-speciality hospitals for immediate resuscitation
    candidates.sort(
        key=lambda c: (
            0 if c.get("is_general_or_multispeciality") else 1,
            c["distance_km"],
        )
    )

    return candidates[0]


@router.post("/sos")
def trigger_sos(
    req: SOSRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """
    Curate the ambulance destination for an SOS.

    Finds the nearest emergency-capable hospital (Postgres + Overpass +
    Geoapify) and returns a dispatch packet: where to go, how far, ETA, the
    hospital phone, and a Google Maps route from the caller's GPS. The client
    opens tel:112 alongside this call; together they let the caller summon
    help AND route it to the right hospital.
    """
    logger.info(
        "SOS dispatch requested by %s at (%s, %s)",
        current_user.email if current_user else "guest",
        req.latitude, req.longitude,
    )

    now = datetime.now(timezone.utc)

    hospital = _find_nearest_emergency_hospital(db, req.latitude, req.longitude)

    if hospital:
        return {
            "status": "dispatched",
            "dispatched": True,
            "message": (
                f"Nearest emergency hospital: {hospital['name']}. "
                "Call 112 from your phone for ambulance dispatch."
            ),
            "emergency_numbers": EMERGENCY_NUMBERS,
            "origin": {
                "latitude": req.latitude,
                "longitude": req.longitude,
                "address": req.address,
                "pincode": req.pincode,
                "google_maps": (
                    f"https://www.google.com/maps?q={req.latitude},{req.longitude}"
                ),
            },
            "destination": hospital,
            "message_from_user": req.message,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }

    # No emergency-capable hospital found in radius: still return an honest
    # acknowledgement with the caller's location and the numbers to dial.
    return {
        "status": "acknowledged",
        "dispatched": False,
        "message": (
            "No emergency hospital found within "
            f"{_SOS_RADIUS_KM:.0f} km. Call 112 from your phone."
        ),
        "emergency_numbers": EMERGENCY_NUMBERS,
        "origin": {
            "latitude": req.latitude,
            "longitude": req.longitude,
            "address": req.address,
            "pincode": req.pincode,
            "google_maps": (
                f"https://www.google.com/maps?q={req.latitude},{req.longitude}"
            ),
        },
        "destination": None,
        "message_from_user": req.message,
        "timestamp": now.isoformat().replace("+00:00", "Z"),
    }
