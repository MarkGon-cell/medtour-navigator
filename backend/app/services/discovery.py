"""
Facility discovery: Overpass + Geoapify, merged into the local directory.

Two external providers, deliberately, because they fail differently:

* **Overpass** (https://wiki.openstreetmap.org/wiki/Overpass_API) is keyless and
  carries the tags the emergency flow needs -- `emergency=*`, `opening_hours`,
  `phone`. But the public mirrors are flaky: on 2026-10-09 every mirror probed
  from this machine returned 500/504 or timed out. So it must never be the
  single point of failure, and a total failure must degrade to local results
  rather than raising.
* **Geoapify** (https://apidocs.geoapify.com/docs) needs a key but is
  operationally reliable, and its terms state *"Cache/store results with no
  limits"* -- which is exactly what this module does. Both draw on
  OpenStreetMap, so combining them buys **availability** redundancy rather
  than extra coverage.

Persistence policy (per product decision, 2026-10-09):

    A facility found by search is written to Postgres **only if it is new**.
    Anything already present is returned but never re-inserted, and existing
    rows are never overwritten -- the CSV import remains the source of record
    for rows it already owns.

Set `GEOAPIFY_API_KEY` in `backend/.env` to enable Geoapify; without it the
provider reports `no_api_key` and discovery runs Overpass-only.
"""

import logging
import os
import re
import time
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.services.geo import bounding_box, haversine_km

load_dotenv()

logger = logging.getLogger(__name__)

GEOAPIFY_PLACES_URL = "https://api.geoapify.com/v2/places"
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")

GOOGLE_PLACES_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
    or os.getenv("GOOGLE_MAPS_DEMO_API_KEY")
)
GOOGLE_PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# Global-scope mirrors only.
OVERPASS_INSTANCES = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

OVERPASS_TIMEOUT_S = 6
GEOAPIFY_TIMEOUT_S = 12
GEOAPIFY_MAX_LIMIT = 500

# Both providers are queried once per rounded area per TTL, so repeated page
# loads do not burn the 3,000/day free Geoapify quota.
CACHE_TTL_S = 15 * 60
_cache: dict[tuple, tuple[float, Any]] = {}

# Deduplication radii.
SAME_SITE_M = 60      # same building: identical facility even if names differ
SAME_NAME_M = 300     # only accepted when the names also look alike

# Anything outside India is discarded before it can reach the table.
INDIA_BOUNDS = (6.0, 67.5, 37.5, 97.5)  # lat_min, lon_min, lat_max, lon_max

# Safety valves: one bad query must not be able to flood the directory.
MAX_PERSIST_PER_CALL = 100
MAX_RESULTS = 500

# `hospitals.state` is NOT NULL but Overpass rarely maps `addr:state`, so when a
# source gives none we fall back to consensus over nearby known rows.
_STATE_CONSENSUS_RADIUS_KM = 15.0
_STATE_MIN_SUPPORT = 3
_STATE_MIN_SHARE = 0.6

_USER_AGENT = "MedTour-Discovery/1.0 (hospital directory crawler)"


@dataclass
class Facility:
    """A facility as reported by an external provider."""

    name: str
    latitude: float
    longitude: float
    source: str
    external_id: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    specialties: Optional[str] = None
    opening_hours: Optional[str] = None
    emergency_available: bool = False
    distance_km: float = 0.0
    # Not persisted: carried through to the response only.
    stored: bool = False
    reason: Optional[str] = None


# ---------------------------------------------------------
# Name matching
# ---------------------------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_LEGAL_SUFFIXES = (
    " limited",
    " ltd",
    " llp",
    " pvt",
    " private",
    " inc",
    " the",
)


def normalize_name(name: Optional[str]) -> str:
    """Lowercase, de-punctuate, and strip corporate suffixes for comparison."""
    text = (name or "").lower().replace("&", " and ")
    text = _NON_ALNUM.sub(" ", text).strip()

    for suffix in _LEGAL_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()

    return text


def names_match(left: Optional[str], right: Optional[str]) -> bool:
    """True when two mapped names plausibly refer to the same facility."""
    a, b = normalize_name(left), normalize_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # "apollo hospital" vs "apollo hospitals for women"
    if len(a) >= 6 and len(b) >= 6 and (a in b or b in a):
        return True
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return False
    return len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b)) >= 0.6


def _coordinates_of(item: Any) -> tuple[float, float]:
    return float(item.latitude), float(item.longitude)


def find_duplicate(
    candidate: Any,
    others: Iterable[Any],
) -> Optional[Any]:
    """
    Return the first existing facility that `candidate` duplicates, else None.

    Works uniformly over `Facility` and the `Hospital` ORM model -- both expose
    latitude/longitude/name/external_id.
    """
    cand_lat, cand_lon = _coordinates_of(candidate)
    cand_name = getattr(candidate, "name", None)
    cand_ext = getattr(candidate, "external_id", None)

    for other in others:
        other_ext = getattr(other, "external_id", None)
        if cand_ext and other_ext and cand_ext == other_ext:
            return other

        other_lat, other_lon = _coordinates_of(other)
        metres = haversine_km(cand_lat, cand_lon, other_lat, other_lon) * 1000.0

        if metres <= SAME_SITE_M:
            return other

        if metres <= SAME_NAME_M and names_match(
            cand_name, getattr(other, "name", None)
        ):
            return other

    return None


# ---------------------------------------------------------
# Provider: Overpass
# ---------------------------------------------------------

def _overpass_query(bbox: tuple[float, float, float, float]) -> str:
    min_lat, max_lat, min_lon, max_lon = bbox
    box = f"({min_lat},{min_lon},{max_lat},{max_lon})"
    # `nwr` covers nodes, ways and relations. A `node[...]` query alone misses
    # most hospitals, which OSM maps as building outlines.
    return (
        "[out:json][timeout:25];"
        "("
        f'nwr["amenity"="hospital"]{box};'
        f'nwr["amenity"="clinic"]{box};'
        f'nwr["healthcare"="hospital"]{box};'
        f'nwr["healthcare"="clinic"]{box};'
        f'nwr["healthcare"="doctor"]{box};'
        f'nwr["emergency"="emergency_ward_entrance"]{box};'
        ");"
        "out center tags;"
    )


def query_overpass(
    latitude: float,
    longitude: float,
    radius_km: float,
    fast: bool = False,
) -> tuple[list[Facility], str]:
    """
    Query every mirror in turn until one answers.

    `fast=True` is for time-critical callers (the /ai/analyze hospital future
    and the /emergency/sos dispatch path). It cuts the per-mirror timeout and
    caps the number of mirrors tried, so a dead Overpass degrades in seconds
    instead of tens of seconds. Those callers still get Geoapify + the local
    directory; they just refuse to wait out every flaky mirror.

    Returns `(facilities, status)` where status is `ok` or `unreachable`.
    Never raises -- a dead provider must not fail the request.
    """
    query = _overpass_query(bounding_box(latitude, longitude, radius_km))
    last_error = ""

    instances = OVERPASS_INSTANCES[:2] if fast else OVERPASS_INSTANCES
    timeout_s = 3 if fast else OVERPASS_TIMEOUT_S

    for instance in instances:
        try:
            response = requests.post(
                instance,
                data={"data": query},
                headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
                timeout=timeout_s,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - mirror failure is expected
            last_error = f"{type(exc).__name__}: {exc}"
            logger.info("Overpass mirror %s failed: %s", instance, last_error)
            continue

        facilities, ward_entrances = _parse_overpass(payload, latitude, longitude)
        _flag_emergency(facilities, ward_entrances)
        logger.info(
            "Overpass %s returned %d facilities", instance, len(facilities)
        )
        return facilities, "ok"

    logger.warning("All Overpass mirrors failed. Last error: %s", last_error)
    return [], "unreachable"


def _parse_overpass(
    payload: dict,
    latitude: float,
    longitude: float,
) -> tuple[list[Facility], list[tuple[float, float]]]:
    facilities: list[Facility] = []
    ward_entrances: list[tuple[float, float]] = []

    for element in payload.get("elements", []):
        tags = element.get("tags") or {}

        centre = element.get("center") or {}
        lat = element.get("lat", centre.get("lat"))
        lon = element.get("lon", centre.get("lon"))
        if lat is None or lon is None:
            continue

        # Emergency-department entrances are markers, not destinations: they
        # get used to flag nearby hospitals rather than listed themselves.
        if tags.get("emergency") == "emergency_ward_entrance":
            ward_entrances.append((float(lat), float(lon)))
            continue

        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue

        healthcare = tags.get("healthcare")
        amenity = tags.get("amenity")

        facility = Facility(
            name=name.strip(),
            latitude=float(lat),
            longitude=float(lon),
            source="overpass",
            external_id=f"osm/{element.get('type', 'node')}/{element.get('id', 0)}",
            address=_overpass_address(tags),
            city=tags.get("addr:city"),
            state=tags.get("addr:state"),
            district=tags.get("addr:district"),
            pincode=tags.get("addr:postcode") or tags.get("contact:postcode"),
            phone=tags.get("phone") or tags.get("contact:phone"),
            website=tags.get("website") or tags.get("contact:website"),
            category=_category_for(amenity, healthcare),
            specialties=tags.get("healthcare:speciality") or tags.get("speciality"),
            opening_hours=tags.get("opening_hours"),
            emergency_available=tags.get("emergency") in ("yes", "true", "24hours"),
        )
        facility.distance_km = haversine_km(
            latitude, longitude, facility.latitude, facility.longitude
        )
        facilities.append(facility)

    return facilities, ward_entrances


def _overpass_address(tags: dict) -> Optional[str]:
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:suburb"),
        tags.get("addr:city"),
    ]
    joined = ", ".join(part for part in parts if part)
    return joined or None


def _category_for(amenity: Optional[str], healthcare: Optional[str]) -> str:
    if amenity == "hospital" or healthcare == "hospital":
        return "Hospital"
    if healthcare == "doctor" or amenity == "doctors":
        return "Doctor"
    if healthcare == "clinic" or amenity == "clinic":
        return "Clinic"
    return "Healthcare"


def _flag_emergency(
    facilities: list[Facility],
    entrances: list[tuple[float, float]],
) -> None:
    """Mark facilities as emergency-capable when a mapped ER entrance is close."""
    if not entrances:
        return
    for facility in facilities:
        if facility.emergency_available:
            continue
        for entrance in entrances:
            if haversine_km(
                facility.latitude, facility.longitude, entrance[0], entrance[1]
            ) <= 0.15:
                facility.emergency_available = True
                break


# ---------------------------------------------------------
# Provider: Geoapify
# ---------------------------------------------------------

_GEOAPIFY_CATEGORIES = (
    "healthcare.hospital",
    "healthcare.clinic_or_praxis",
    # Also fetched, but only used as an emergency-capability marker.
    "emergency.emergency_ward_entrance",
)


def query_geoapify(
    latitude: float,
    longitude: float,
    radius_km: float,
    fast: bool = False,
) -> tuple[list[Facility], str]:
    """
    Query the Geoapify Places API.

    `fast=True` shortens the timeout for time-critical callers (/ai/analyze
    hospital future, /emergency/sos). Geoapify is the reliable provider, so
    unlike Overpass we still try it in fast mode -- just with a tighter budget.

    Returns `(facilities, status)` where status is one of `ok`, `no_api_key`,
    `rate_limited` or `error`. Never raises.
    """
    if not GEOAPIFY_API_KEY:
        return [], "no_api_key"

    params = {
        "categories": ",".join(_GEOAPIFY_CATEGORIES),
        # Geoapify takes a circle as lon,lat,RADIUS IN METRES.
        "filter": f"circle:{longitude},{latitude},{int(radius_km * 1000)}",
        "bias": f"proximity:{longitude},{latitude}",
        "limit": GEOAPIFY_MAX_LIMIT,
        "lang": "en",
        "apiKey": GEOAPIFY_API_KEY,
    }

    try:
        response = requests.get(
            GEOAPIFY_PLACES_URL,
            params=params,
            headers={"User-Agent": _USER_AGENT},
            # Geoapify is the RELIABLE provider, so fast mode keeps a real
            # budget for it -- only the flaky Overpass mirrors get the hard
            # cut. Must stay under the /ai/analyze hospital future (18s) once
            # Overpass fast (2x3s) is accounted for.
            timeout=8 if fast else GEOAPIFY_TIMEOUT_S,
        )
        if response.status_code == 429:
            logger.warning("Geoapify rate limit hit")
            return [], "rate_limited"
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
        logger.warning("Geoapify failed: %s: %s", type(exc).__name__, exc)
        return [], "error"

    return _parse_geoapify(payload, latitude, longitude)


def query_google_places(
    latitude: float,
    longitude: float,
    radius_km: float,
    fast: bool = False,
) -> tuple[list[Facility], str]:
    """
    Query Google Places API (New) for hospitals, clinics, and emergency medical centers.
    Discovers multi-speciality, multispeciality, and general hospitals directly from Google Places.
    """
    if not GOOGLE_PLACES_KEY:
        return [], "no_api_key"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_PLACES_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.location,places.formattedAddress,"
            "places.nationalPhoneNumber,places.internationalPhoneNumber,places.types,"
            "places.rating,places.userRatingCount,places.websiteUri,places.regularOpeningHours"
        ),
    }
    payload = {
        "includedTypes": ["hospital"],
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": min(radius_km, 50.0) * 1000.0,
            }
        },
        "maxResultCount": 20,
    }

    try:
        resp = requests.post(
            GOOGLE_PLACES_NEARBY_URL,
            headers=headers,
            json=payload,
            timeout=5 if fast else 8,
        )
        if resp.status_code in (401, 403):
            logger.warning("Google Places authentication/quota issue: %s", resp.status_code)
            return [], f"auth_{resp.status_code}"
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Google Places Nearby query failed: %s: %s", type(exc).__name__, exc)
        return [], "error"

    facilities: list[Facility] = []
    for place in data.get("places", []):
        display_name = (place.get("displayName") or {}).get("text")
        if not display_name:
            continue
        loc = place.get("location") or {}
        p_lat, p_lon = loc.get("latitude"), loc.get("longitude")
        if p_lat is None or p_lon is None:
            continue

        addr = place.get("formattedAddress") or ""
        phone = place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber")
        web = place.get("websiteUri")
        types = place.get("types") or []

        # Check emergency / 24-7 capability
        is_24_7 = False
        hours = place.get("regularOpeningHours") or {}
        periods = hours.get("periods") or []
        for period in periods:
            open_h = period.get("open", {})
            if open_h.get("hour") == 0 and open_h.get("minute") == 0 and not period.get("close"):
                is_24_7 = True
                break

        name_lower = display_name.lower()
        is_multi_or_gen = any(
            k in name_lower
            for k in ["multi", "general", "civil", "district", "trauma", "tertiary", "superspeciality"]
        )

        fac = Facility(
            name=display_name.strip(),
            latitude=float(p_lat),
            longitude=float(p_lon),
            source="google_places",
            external_id=place.get("id"),
            address=addr,
            phone=phone,
            website=web,
            category="Hospital",
            emergency_available=is_24_7 or is_multi_or_gen,
            distance_km=haversine_km(latitude, longitude, float(p_lat), float(p_lon)),
        )
        facilities.append(fac)

    return facilities, "ok"


def _parse_geoapify(
    payload: dict,
    latitude: float,
    longitude: float,
) -> tuple[list[Facility], str]:
    facilities: list[Facility] = []
    ward_entrances: list[tuple[float, float]] = []

    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        categories = props.get("categories") or []

        lat, lon = props.get("lat"), props.get("lon")
        if lat is None or lon is None:
            continue

        if any(cat.startswith("emergency.") for cat in categories):
            ward_entrances.append((float(lat), float(lon)))
            continue

        name = props.get("name")
        if not name:
            continue

        facility = Facility(
            name=str(name).strip(),
            latitude=float(lat),
            longitude=float(lon),
            source="geoapify",
            external_id=props.get("place_id"),
            address=props.get("formatted") or props.get("address_line1"),
            city=props.get("city"),
            state=props.get("state"),
            district=props.get("county") or props.get("district"),
            pincode=props.get("postcode"),
            category=_geoapify_category(categories),
            specialties=_geoapify_specialty(categories),
            # Geoapify Places does not return phone numbers; those come from
            # Overpass tags or the local directory. Place Details is a
            # separately billed call and is not made here.
        )
        if props.get("distance") is not None:
            facility.distance_km = float(props["distance"]) / 1000.0
        else:
            facility.distance_km = haversine_km(
                latitude, longitude, facility.latitude, facility.longitude
            )
        facilities.append(facility)

    _flag_emergency(facilities, ward_entrances)
    return facilities, "ok"


def _geoapify_category(categories: list[str]) -> str:
    if "healthcare.hospital" in categories:
        return "Hospital"
    if any(cat.startswith("healthcare.clinic_or_praxis") for cat in categories):
        return "Clinic"
    return "Healthcare"


def _geoapify_specialty(categories: list[str]) -> Optional[str]:
    specialities = [
        cat.split(".", 1)[1].replace("_", " ")
        for cat in categories
        if cat.startswith("healthcare.clinic_or_praxis.")
    ]
    return ", ".join(sorted(set(specialities))) or None


# ---------------------------------------------------------
# Caching
# ---------------------------------------------------------

def _cache_get(key: tuple) -> Any:
    entry = _cache.get(key)
    if entry is None:
        return None
    stamp, value = entry
    if time.time() - stamp > CACHE_TTL_S:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: tuple, value: Any) -> None:
    # Two-decimal rounding is ~1.1 km, tight enough that results stay relevant
    # while still letting repeated scrolls of the same area hit the cache.
    if len(_cache) > 512:
        _cache.clear()
    _cache[key] = (time.time(), value)


def _cached_fetch(
    provider: str,
    latitude: float,
    longitude: float,
    radius_km: float,
    fetch: Callable[..., tuple[list[Facility], str]],
    fast: bool = False,
) -> tuple[list[Facility], str]:
    key = (
        provider,
        round(latitude, 2),
        round(longitude, 2),
        round(radius_km, 1),
        # Fast calls may hit fewer mirrors and get a thinner result; keep them
        # in a separate bucket so a full-budget caller never reads a fast entry.
        fast,
    )
    cached = _cache_get(key)
    if cached is not None:
        # The cache holds the (facilities, status) pair. Unpack it -- returning
        # the pair itself makes `overpass_rows + geoapify_rows` blow up with
        # "can only concatenate list (not tuple)", which only ever happens on a
        # cache HIT, i.e. the second request within the TTL.
        facilities, _cached_status = cached
        return facilities, "cached"

    if fast:
        facilities, status = fetch(latitude, longitude, radius_km, fast=True)
    else:
        facilities, status = fetch(latitude, longitude, radius_km)
    if status in ("ok", "no_api_key"):
        _cache_put(key, (facilities, status))
    return facilities, status


def clear_cache() -> None:
    """Exposed for tests."""
    _cache.clear()


# ---------------------------------------------------------
# Persistence
# ---------------------------------------------------------

def _in_india(latitude: float, longitude: float) -> bool:
    lat_min, lon_min, lat_max, lon_max = INDIA_BOUNDS
    return lat_min <= latitude <= lat_max and lon_min <= longitude <= lon_max


def _looks_usable(facility: Facility) -> Optional[str]:
    """Return a rejection reason, or None when the row is safe to store."""
    if not facility.name or len(facility.name.strip()) < 3:
        return "missing_name"
    if not _in_india(facility.latitude, facility.longitude):
        return "outside_india"
    return None


def state_consensus(
    latitude: float,
    longitude: float,
    rows: Iterable[Any],
) -> Optional[str]:
    """
    The state supported by a supermajority of rows within
    `_STATE_CONSENSUS_RADIUS_KM`, or None when the evidence is thin.

    Works over `Facility` and `Hospital` alike -- both expose `state`,
    `latitude` and `longitude`. Shared by `_infer_state` and
    `scripts/repair_discovery_state.py` so the repair path cannot drift from
    the write path.
    """
    counts: Counter = Counter()
    for row in rows:
        if not row.state:
            continue
        if haversine_km(latitude, longitude, row.latitude, row.longitude) <= (
            _STATE_CONSENSUS_RADIUS_KM
        ):
            counts[row.state.strip()] += 1

    total = sum(counts.values())
    if total < _STATE_MIN_SUPPORT:
        return None

    winner, votes = counts.most_common(1)[0]
    if votes / total < _STATE_MIN_SHARE:
        return None

    return winner


def _infer_state(
    facility: Facility,
    batch: Iterable[Facility],
) -> Optional[str]:
    """
    `hospitals.state` is NOT NULL, but Overpass only tags `addr:state` on some
    facilities (181 of 214 around Lucknow when measured).

    Prefer the value the provider actually reported for *this* facility. Failing
    that, take a supermajority vote over the **same provider batch**.

    Two things are deliberate here.

    **We vote over the provider batch, never over the local directory.** The
    CSV's own `state` column is corrupt -- all six Lucknow rows it ships read
    "Bihar", "Chhattisgarh", "Haryana" or "Jammu and Kashmir", none of them
    "Uttar Pradesh". An earlier version of this function copied the nearest
    directory row's state and so stamped two discovered Lucknow facilities as
    being in Haryana and Jammu & Kashmir. The provider batch is the population
    that actually knows about this city; the directory is not.

    **A bare plurality is not enough.** We require a supermajority, so a batch
    whose states are genuinely split reports nothing. An unknown state is better
    than a fabricated one.
    """
    if facility.state:
        return facility.state

    return state_consensus(facility.latitude, facility.longitude, batch)


def _to_hospital(facility: Facility, batch: Iterable[Facility]) -> Hospital:
    return Hospital(
        name=facility.name.strip(),
        category=facility.category,
        care_type="Curated",
        city=facility.city,
        # NOT NULL in the schema: fall back to "" rather than failing the write.
        state=_infer_state(facility, batch) or "",
        district=facility.district,
        address=facility.address,
        pincode=facility.pincode,
        latitude=facility.latitude,
        longitude=facility.longitude,
        specialties=facility.specialties,
        emergency_available=facility.emergency_available,
        emergency_services=(
            "Emergency department mapped in OSM"
            if facility.emergency_available
            else None
        ),
        phone=facility.phone,
        website=facility.website,
        source=facility.source,
        external_id=facility.external_id,
        opening_hours=facility.opening_hours,
    )


def persist_new(
    db: Session,
    facilities: list[Facility],
    existing: list[Hospital],
) -> tuple[list[Hospital], int, int]:
    """
    Insert facilities that are not already in the directory.

    Existing rows are never updated -- per product decision, search only adds
    new facilities. Returns `(inserted, skipped_existing, skipped_invalid)`.
    """
    skipped_existing = 0
    skipped_invalid = 0
    inserted: list[Hospital] = []

    # Pool grows as we insert, so a batch cannot contain two copies of the
    # same place when Overpass and Geoapify both report it.
    pool: list[Any] = list(existing)

    for facility in facilities:
        reason = _looks_usable(facility)
        if reason:
            facility.reason = reason
            skipped_invalid += 1
            continue

        if find_duplicate(facility, pool) is not None:
            facility.reason = "already_in_directory"
            facility.stored = False
            skipped_existing += 1
            continue

        if len(inserted) >= MAX_PERSIST_PER_CALL:
            facility.reason = "persist_limit_reached"
            facility.stored = False
            continue

        # State is inferred from the provider batch (`facilities`), never from
        # `existing` -- see `_infer_state`. The directory's own state column is
        # corrupt in places and must not vote.
        row = _to_hospital(facility, facilities)
        db.add(row)
        pool.append(row)
        inserted.append(row)
        facility.stored = True
        facility.reason = None

    if inserted:
        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to persist %d new facilities", len(inserted))
            for facility in facilities:
                facility.stored = False
                facility.reason = "persist_failed"
            return [], 0, skipped_invalid

    return inserted, skipped_existing, skipped_invalid


# ---------------------------------------------------------
# Payload
# ---------------------------------------------------------

def _payload(facility: Facility) -> dict:
    return {
        "name": facility.name,
        "category": facility.category,
        "city": facility.city,
        "state": facility.state,
        "district": facility.district,
        "address": facility.address,
        "pincode": facility.pincode,
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "specialties": facility.specialties,
        "emergency_available": facility.emergency_available,
        "phone": facility.phone,
        "website": facility.website,
        "opening_hours": facility.opening_hours,
        "distance_km": round(facility.distance_km, 2),
        "origin": facility.source,
        "external_id": facility.external_id,
        "stored": facility.stored,
        "stored_reason": facility.reason,
    }


def _local_payload(row: Hospital, distance_km: float) -> dict:
    return {
        "name": row.name,
        "category": row.category,
        "city": row.city,
        "state": row.state,
        "district": row.district,
        "address": row.address,
        "pincode": row.pincode,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "specialties": row.specialties,
        "emergency_available": row.emergency_available,
        "phone": row.phone,
        "website": row.website,
        "opening_hours": row.opening_hours,
        "distance_km": round(distance_km, 2),
        "origin": "local",
        "external_id": row.external_id,
        "stored": True,
        "stored_reason": None,
    }


# ---------------------------------------------------------
# Orchestration
# ---------------------------------------------------------

def discover(
    db: Session,
    latitude: float,
    longitude: float,
    radius_km: float,
    persist: bool = True,
    limit: Optional[int] = None,
    fast: bool = False,
) -> dict:
    """
    Merge local + Overpass + Geoapify results and optionally store the new ones.

    `fast=True` is for time-critical callers (the /ai/analyze hospital future
    and /emergency/sos): Overpass uses a short timeout and few mirrors, and
    Geoapify a tighter budget, so a dead provider degrades in seconds. The
    interactive /hospitals/discover browse keeps the full retry budget.
    """
    min_lat, max_lat, min_lon, max_lon = bounding_box(
        latitude, longitude, radius_km
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

    overpass_rows, overpass_status = _cached_fetch(
        "overpass", latitude, longitude, radius_km, query_overpass, fast=fast
    )
    geoapify_rows, geoapify_status = _cached_fetch(
        "geoapify", latitude, longitude, radius_km, query_geoapify, fast=fast
    )
    google_places_rows, google_places_status = _cached_fetch(
        "google_places", latitude, longitude, radius_km, query_google_places, fast=fast
    )

    # Existing rows win: never re-store what we already hold.
    new_candidates: list[Facility] = []
    duplicate_count = 0
    pool: list[Any] = list(local_rows)

    for facility in google_places_rows + overpass_rows + geoapify_rows:
        facility.distance_km = haversine_km(
            latitude, longitude, facility.latitude, facility.longitude
        )
        if facility.distance_km > radius_km:
            continue
        if find_duplicate(facility, pool) is not None:
            facility.reason = "already_in_directory"
            duplicate_count += 1
            continue
        pool.append(facility)
        new_candidates.append(facility)

    inserted: list[Hospital] = []
    persisted = 0
    skipped_invalid = 0
    if new_candidates:
        if persist:
            inserted, _skipped_existing, skipped_invalid = persist_new(
                db, new_candidates, local_rows
            )
            persisted = len(inserted)
        else:
            for facility in new_candidates:
                facility.reason = "persist_disabled"
                facility.stored = False

    results = [_local_payload(row, _distance(latitude, longitude, row)) for row in local_rows]
    results.extend(_payload(facility) for facility in new_candidates)

    results.sort(key=lambda item: item["distance_km"])
    results = results[: limit or MAX_RESULTS]

    return {
        "results": results,
        "sources": {
            "local": "ok",
            "overpass": overpass_status,
            "geoapify": geoapify_status,
        },
        "stats": {
            "returned": len(results),
            "local": len(local_rows),
            "overpass": len(overpass_rows),
            "geoapify": len(geoapify_rows),
            "duplicates_dropped": duplicate_count,
            "persisted": persisted,
            "rejected": skipped_invalid,
        },
        "degraded": overpass_status not in ("ok", "cached")
        and geoapify_status not in ("ok", "cached"),
    }


def _distance(latitude: float, longitude: float, row: Hospital) -> float:
    return haversine_km(latitude, longitude, row.latitude, row.longitude)
