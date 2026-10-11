"""
Shared geodesy for facility search.

Kept in one place because `GET /hospitals/nearby`, `GET /hospitals/discover`
and the dedupe logic in `app.services.discovery` must all agree on what
"the same facility" means. A duplicated implementation is how you end up with
one caller silently dropping rows.

Regression-tested by backend/tests_api/test_geo_helpers.py.
"""

from math import atan2, cos, radians, sin, sqrt

# Mean Earth radius in km.
EARTH_RADIUS_KM = 6371.0


def haversine_km(
    latitude: float,
    longitude: float,
    other_latitude: float,
    other_longitude: float,
) -> float:
    """Great-circle distance between two WGS84 points, in kilometres."""
    lat1 = radians(latitude)
    lat2 = radians(other_latitude)

    # NOTE: subtract raw degrees, then convert. Converting lat1/lat2 first and
    # feeding the radian pair back into radians() understates distance ~6x.
    delta_lat = radians(other_latitude - latitude)
    delta_lon = radians(other_longitude - longitude)

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )

    return EARTH_RADIUS_KM * 2 * atan2(sqrt(a), sqrt(1 - a))


def bounding_box(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> tuple[float, float, float, float]:
    """
    Cheap lat/lon envelope that certainly contains every point within
    `radius_km`. Used as a SQL-level pre-filter so the exact haversine
    only runs over candidates, instead of over the whole table.

    Returned as (min_lat, max_lat, min_lon, max_lon).
    """
    # 1 degree of latitude is ~110.574 km; of longitude ~111.320 km at the
    # equator, shrinking with cos(latitude).
    delta_lat = radius_km / 110.574

    cos_lat = max(abs(cos(radians(latitude))), 1e-6)
    delta_lon = radius_km / (111.320 * cos_lat)

    return (
        latitude - delta_lat,
        latitude + delta_lat,
        longitude - delta_lon,
        longitude + delta_lon,
    )
