"""
Evidence check: does Overpass/OSM actually cover the Indian cities our local
directory cannot (Delhi, UP, TN, WB, Rajasthan...)? Run before deciding the
discovery source -- see docs/architecture.md section 5.0.

Read-only, polite: one lightweight `out count` query per city with a pause.
"""

import time

import requests

OVERPASS = "https://overpass-api.de/api/interpreter"

CITIES = [
    ("Delhi", 28.6139, 77.2090),
    ("Lucknow", 26.8467, 80.9462),
    ("Chennai", 13.0827, 80.2707),
    ("Kolkata", 22.5726, 88.3639),
    ("Jaipur", 26.9124, 75.7873),
    ("Mumbai", 19.0760, 72.8777),
]

# 0.15 degrees ~ 16km box, roughly a city.
SPAN = 0.15

HEADERS = {
    "User-Agent": "MedTour-data-audit/1.0 (one-off coverage probe)",
    "Accept": "application/json",
}


def count(selector: str, bbox: str) -> int:
    query = f"[out:json][timeout:25];nwr{selector}({bbox});out count;"
    response = requests.post(
        OVERPASS,
        data={"data": query},
        headers=HEADERS,
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    return sum(element.get("count", 0) for element in body.get("elements", []))


def main() -> None:
    print(f"{'city':10} {'hospitals':>10} {'clinics':>8} {'doctors':>8}")
    print("-" * 40)

    for name, lat, lon in CITIES:
        bbox = f"{lat - SPAN},{lon - SPAN},{lat + SPAN},{lon + SPAN}"
        try:
            hospitals = count('["amenity"="hospital"]', bbox)
            clinics = count('["healthcare"="clinic"]', bbox)
            doctors = count('["healthcare"="doctor"]', bbox)
            print(f"{name:10} {hospitals:>10} {clinics:>8} {doctors:>8}")
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"{name:10} ERROR: {exc}")
        time.sleep(2)


if __name__ == "__main__":
    main()
