import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

type NearbyHospital = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  address?: string;
  emergency?: string;
};

type NearbyHospitalMapProps = {
  radiusKm?: number;
};

export function NearbyHospitalMap({
  radiusKm = 10,
}: NearbyHospitalMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.LayerGroup | null>(null);

  const [hospitals, setHospitals] = useState<NearbyHospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [locationError, setLocationError] = useState("");

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) {
      return;
    }

    const map = L.map(mapContainerRef.current).setView(
      [20.5937, 78.9629],
      5
    );

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }
    ).addTo(map);

    markersRef.current = L.layerGroup().addTo(map);

    mapRef.current = map;

    const locateUser = () => {
      setLoading(true);
      setLocationError("");

      navigator.geolocation.getCurrentPosition(
        async (position) => {
          const latitude = position.coords.latitude;
          const longitude = position.coords.longitude;

          map.setView([latitude, longitude], 13);

          L.circleMarker([latitude, longitude], {
            radius: 8,
            color: "#0f766e",
            fillColor: "#14b8a6",
            fillOpacity: 0.9,
          })
            .addTo(map)
            .bindPopup("<b>Your Location</b>")
            .openPopup();

          try {
            const radiusMeters = radiusKm * 1000;

            const query = `
              [out:json][timeout:25];

              (
                node["amenity"="hospital"](around:${radiusMeters},${latitude},${longitude});
                way["amenity"="hospital"](around:${radiusMeters},${latitude},${longitude});
                relation["amenity"="hospital"](around:${radiusMeters},${latitude},${longitude});
              );

              out center tags;
            `;

            const response = await fetch(
              "https://overpass-api.de/api/interpreter",
              {
                method: "POST",
                body: query,
              }
            );

            if (!response.ok) {
              throw new Error("Hospital search failed");
            }

            const data = await response.json();

            const results: NearbyHospital[] = data.elements
              .map((element: any) => {
                const lat =
                  element.lat ?? element.center?.lat;

                const lon =
                  element.lon ?? element.center?.lon;

                if (!lat || !lon) {
                  return null;
                }

                return {
                  id: `${element.type}-${element.id}`,
                  name:
                    element.tags?.name ||
                    "Unnamed Hospital",
                  latitude: lat,
                  longitude: lon,
                  address:
                    element.tags?.["addr:full"] ||
                    element.tags?.["addr:street"],
                  emergency:
                    element.tags?.emergency,
                };
              })
              .filter(Boolean);

            setHospitals(results);

            markersRef.current?.clearLayers();

            results.forEach((hospital) => {
              const marker = L.marker([
                hospital.latitude,
                hospital.longitude,
              ]);

              const googleMapsUrl =
                `https://www.google.com/maps/dir/?api=1` +
                `&destination=${hospital.latitude},${hospital.longitude}`;

              marker.bindPopup(`
                <div style="min-width:220px">
                  <strong>${hospital.name}</strong>

                  ${
                    hospital.address
                      ? `<p style="margin:6px 0">${hospital.address}</p>`
                      : ""
                  }

                  ${
                    hospital.emergency
                      ? `<p style="margin:6px 0">
                           Emergency: ${hospital.emergency}
                         </p>`
                      : ""
                  }

                  <a
                    href="${googleMapsUrl}"
                    target="_blank"
                    rel="noopener noreferrer"
                    style="
                      display:inline-block;
                      margin-top:8px;
                      padding:6px 10px;
                      background:#0f766e;
                      color:white;
                      border-radius:6px;
                      text-decoration:none;
                    "
                  >
                    Navigate
                  </a>
                </div>
              `);

              marker.addTo(markersRef.current!);
            });
          } catch (error) {
            console.error(error);
            setLocationError(
              "Unable to find nearby hospitals."
            );
          } finally {
            setLoading(false);
          }
        },
        (error) => {
          console.error(error);

          setLocationError(
            "Location permission is required to find nearby hospitals."
          );

          setLoading(false);
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000,
        }
      );
    };

    locateUser();

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [radiusKm]);

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card">
      <div className="grid lg:grid-cols-[320px_1fr]">

        {/* Hospital list */}
        <div className="max-h-[600px] overflow-y-auto border-r border-border">
          <div className="border-b border-border p-5">
            <h2 className="font-semibold">
              Nearby Hospitals
            </h2>

            <p className="mt-1 text-xs text-muted-foreground">
              Hospitals within {radiusKm} km of your location
            </p>

            {loading && (
              <p className="mt-3 text-xs text-muted-foreground">
                Finding your location...
              </p>
            )}

            {locationError && (
              <p className="mt-3 text-xs text-destructive">
                {locationError}
              </p>
            )}
          </div>

          <div className="p-3">
            {!loading && hospitals.length === 0 && !locationError && (
              <p className="p-4 text-sm text-muted-foreground">
                No hospitals found nearby.
              </p>
            )}

            {hospitals.map((hospital) => (
              <button
                key={hospital.id}
                className="mb-2 w-full rounded-xl border border-border/70 p-4 text-left transition hover:bg-muted"
                onClick={() => {
                  mapRef.current?.setView(
                    [hospital.latitude, hospital.longitude],
                    16
                  );
                }}
              >
                <p className="font-medium">
                  {hospital.name}
                </p>

                {hospital.address && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {hospital.address}
                  </p>
                )}

                <div className="mt-3 flex gap-2">
                  <span className="text-xs text-primary">
                    View on map
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Map */}
        <div className="relative min-h-[500px]">
          <div
            ref={mapContainerRef}
            className="h-[600px] w-full"
          />

          {/* Map status */}
          <div className="absolute left-4 top-4 z-[1000] rounded-lg bg-background/95 px-4 py-2 shadow">
            <p className="text-xs font-medium">
              {loading
                ? "Finding nearby hospitals..."
                : `${hospitals.length} hospitals found`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}