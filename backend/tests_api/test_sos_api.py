import json
import sys

import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000"


def test_sos_returns_dispatch_packet():
    """
    SOS must curate the ambulance destination: the nearest emergency-capable
    hospital with distance, ETA and a Google Maps route from the caller.

    The client opens tel:112 alongside this call; this endpoint tells the
    caller where to go. See docs/architecture.md section 4.
    """
    print("\n--- Testing Emergency SOS API ---")
    payload = {
        "latitude": 19.3719,
        "longitude": 72.8220,
        "address": "Vasai West, Palghar, Maharashtra, India",
        "pincode": "401202",
        "message": "Chest pain and shortness of breath",
        "contact_emergency_services": True,
    }

    response = requests.post(f"{BASE_URL}/emergency/sos", json=payload, timeout=30)
    print(f"Status Code: {response.status_code}")
    print("Response JSON:")
    print(json.dumps(response.json(), indent=2))

    assert response.status_code == 200

    body = response.json()
    assert body["emergency_numbers"]["national_emergency"] == "112"
    assert "origin" in body and "destination" in body

    dest = body.get("destination")
    if body["dispatched"]:
        # A destination was found: it must carry the routing the client shows.
        assert dest is not None
        for key in ("name", "distance_km", "eta_minutes", "google_maps_route"):
            assert key in dest, f"destination missing {key}"
        assert dest["eta_minutes"] >= 1
        assert "google.com/maps/dir" in dest["google_maps_route"]
    else:
        # Honest fallback when nothing emergency-capable is within radius.
        assert dest is None

    serialised = json.dumps(body)
    assert "simulated" not in serialised

    print("✅ SOS endpoint returns a dispatch packet to the nearest ER.")


if __name__ == "__main__":
    test_sos_returns_dispatch_packet()
