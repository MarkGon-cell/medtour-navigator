"""Which Overpass instances are reachable and how fast? Read-only, one query each."""

import time

import requests

QUERY = '[out:json][timeout:25];nwr["amenity"="hospital"](28.46,77.06,28.76,77.36);out count;'

INSTANCES = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

HEADERS = {"User-Agent": "MedTour-data-audit/1.0"}


def main() -> None:
    for base in INSTANCES:
        start = time.perf_counter()
        try:
            response = requests.post(
                base,
                data={"data": QUERY},
                headers=HEADERS,
                timeout=60,
            )
            elapsed = time.perf_counter() - start
            if response.ok:
                total = sum(
                    element.get("count", 0)
                    for element in response.json().get("elements", [])
                )
                print(f"{base:50} {response.status_code}  {elapsed:5.1f}s  delhi_hospitals={total}")
            else:
                print(f"{base:50} {response.status_code}  {elapsed:5.1f}s  {response.text[:60]}")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            print(f"{base:50} ERR   {elapsed:5.1f}s  {type(exc).__name__}: {exc}")
        time.sleep(3)


if __name__ == "__main__":
    main()
