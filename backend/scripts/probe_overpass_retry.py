"""Single-city Overpass probe with backoff: is the instance down, or is India just unmapped?

Answering this matters: "0 hospitals" and "API unreachable" mean opposite things
for the discovery design in docs/architecture.md section 5.1.
"""

import time

import requests

INSTANCES = [
    "https://overpass-api.de/api/interpreter",
]

CITIES = [
    ("Delhi", 28.6139, 77.2090),
    ("Chennai", 13.0827, 80.2707),
    ("Mumbai", 19.0760, 72.8777),
]

SPAN = 0.15
HEADERS = {"User-Agent": "MedTour-data-audit/1.0"}
ATTEMPTS = 3


def fetch(base: str, selector: str, bbox: str) -> int | None:
    query = f"[out:json][timeout:25];nwr{selector}({bbox});out count;"
    for attempt in range(1, ATTEMPTS + 1):
        try:
            response = requests.post(
                base,
                data={"data": query},
                headers=HEADERS,
                timeout=60,
            )
            response.raise_for_status()
            return sum(
                element.get("count", 0)
                for element in response.json().get("elements", [])
            )
        except Exception as exc:  # noqa: BLE001
            print(f"      attempt {attempt}/{ATTEMPTS} -> {type(exc).__name__}: {str(exc)[:70]}")
            if attempt < ATTEMPTS:
                time.sleep(10 * attempt)
    return None


def main() -> None:
    for base in INSTANCES:
        print(f"\n=== {base} ===")
        for name, lat, lon in CITIES:
            bbox = f"{lat - SPAN},{lon - SPAN},{lat + SPAN},{lon + SPAN}"
            hospitals = fetch(base, '["amenity"="hospital"]', bbox)
            if hospitals is None:
                print(f"  {name:9} UNREACHABLE after {ATTEMPTS} attempts")
                continue
            print(f"  {name:9} hospitals={hospitals}")
            time.sleep(5)
        time.sleep(10)


if __name__ == "__main__":
    main()
