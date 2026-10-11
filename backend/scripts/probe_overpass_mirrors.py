"""Reachability + India coverage check for candidate Overpass mirrors.

Read-only. Answers two questions per instance: (1) is it up, (2) does it
actually return Indian facilities -- overpass.osm.ch answered instantly but is
scoped to Switzerland, so a 200 alone proves nothing.
"""

import time

import requests

INSTANCES = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
]

# Delhi city centre, +/-0.05 deg (~5km) -- small to stay polite.
BBOX = "28.56,77.16,28.66,77.26"
QUERY = f'[out:json][timeout:20];nwr["amenity"="hospital"]({BBOX});out count;'

HEADERS = {"User-Agent": "MedTour-data-audit/1.0"}
TIMEOUT = 30


def main() -> None:
    print(f"{'instance':55} {'status':>7} {'sec':>6} {'delhi_hospitals':>16}")
    print("-" * 90)

    for base in INSTANCES:
        start = time.perf_counter()
        try:
            response = requests.post(
                base,
                data={"data": QUERY},
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            elapsed = time.perf_counter() - start
            if response.ok:
                try:
                    total = sum(
                        element.get("count", 0)
                        for element in response.json().get("elements", [])
                    )
                except ValueError:
                    total = "non-json"
                print(f"{base:55} {response.status_code:>7} {elapsed:6.1f} {str(total):>16}")
            else:
                print(f"{base:55} {response.status_code:>7} {elapsed:6.1f} {'-':>16}")
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            print(f"{base:55} {'ERR':>7} {elapsed:6.1f} {type(exc).__name__[:14]:>16}")
        time.sleep(2)


if __name__ == "__main__":
    main()
