import { useEffect, useRef, useState } from "react";
import type { Map, LayerGroup, Marker } from "leaflet";
import "leaflet/dist/leaflet.css";
import api from "@/lib/api";

type NearbyHospital = {
  id: number;
  name: string;
  city: string;
  state: string;
  address: string;
  latitude: number;
  longitude: number;

  specialties?: string | null;
  languages?: string | null;
  consultation_fee?: number | null;
  waiting_time?: number | null;
  emergency_available: boolean;
  icu_available: boolean;
  rating?: number | null;
  phone?: string | null;
  distance_km?: number;
};

type NearbyHospitalMapProps = {
  radiusKm?: number;
};

export function NearbyHospitalMap({
  radiusKm = 10,
}: NearbyHospitalMapProps) {
  const mapContainerRef =
    useRef<HTMLDivElement | null>(null);

  const mapRef = useRef<Map | null>(null);

  const markersRef =
    useRef<LayerGroup | null>(null);

  const hospitalMarkersRef = useRef<
    globalThis.Map<number, Marker>
  >(new globalThis.Map());

  const leafletRef =
    useRef<typeof import("leaflet") | null>(null);

  const userLocationRef = useRef<{
    latitude: number;
    longitude: number;
  } | null>(null);

  const [hospitals, setHospitals] =
    useState<NearbyHospital[]>([]);

  const [search, setSearch] =
    useState("");

  const [selectedRadius, setSelectedRadius] =
    useState(radiusKm);

  const [loading, setLoading] =
    useState(true);

  const [locationError, setLocationError] =
    useState("");

  const [emergencyOnly, setEmergencyOnly] =
    useState(false);

  const [specialtyFilter, setSpecialtyFilter] =
    useState("all");

  /*
   * Fetch hospitals from FastAPI.
   *
   * FastAPI + PostgreSQL handle:
   * - Distance
   * - Radius
   * - Specialty
   * - Emergency availability
   */
  const fetchHospitals = async (
    latitude: number,
    longitude: number,
    radius: number,
    specialty: string,
    emergency: boolean
  ) => {
    try {
      setLoading(true);
      setLocationError("");

      const response =
        await api.get<NearbyHospital[]>(
          "/hospitals/nearby",
          {
            params: {
              latitude,
              longitude,
              radius_km: radius,

              specialty:
                specialty === "all"
                  ? undefined
                  : specialty,

              emergency,
            },
          }
        );

      console.log(
        "Hospitals from backend:",
        response.data
      );

      setHospitals(response.data);
    } catch (error) {
      console.error(
        "Failed to fetch nearby hospitals:",
        error
      );

      setHospitals([]);

      setLocationError(
        "Unable to find nearby hospitals. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  /*
   * INITIALIZE LEAFLET
   *
   * IMPORTANT:
   * Leaflet is dynamically imported here so it
   * only runs in the browser.
   *
   * This prevents:
   * "window is not defined"
   */
  useEffect(() => {
    let cancelled = false;

    const initializeMap = async () => {
      if (
        !mapContainerRef.current ||
        mapRef.current
      ) {
        return;
      }

      try {
        /*
         * Load Leaflet only on the client.
         */
        const L =
          await import("leaflet");

        if (cancelled) {
          return;
        }

        leafletRef.current = L;

        /*
         * Create map.
         */
        const map = L.map(
          mapContainerRef.current
        ).setView(
          [20.5937, 78.9629],
          5
        );

        /*
         * OpenStreetMap tiles.
         */
        L.tileLayer(
          "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
          {
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          }
        ).addTo(map);

        /*
         * Marker layer.
         */
        const markerLayer =
          L.layerGroup().addTo(map);

        markersRef.current =
          markerLayer;

        mapRef.current = map;

        /*
         * Get user's current location.
         */
        if (!navigator.geolocation) {
          setLocationError(
            "Geolocation is not supported by this browser."
          );

          setLoading(false);

          return;
        }

        navigator.geolocation.getCurrentPosition(
          async (position) => {
            if (cancelled) {
              return;
            }

            const latitude =
              position.coords.latitude;

            const longitude =
              position.coords.longitude;

            userLocationRef.current = {
              latitude,
              longitude,
            };

            /*
             * Center map on user.
             */
            map.setView(
              [latitude, longitude],
              13
            );

            /*
             * User location marker.
             */
            L.circleMarker(
              [latitude, longitude],
              {
                radius: 8,
                color: "#0f766e",
                fillColor: "#14b8a6",
                fillOpacity: 0.9,
                weight: 2,
              }
            )
              .addTo(map)
              .bindPopup(
                "<b>Your Location</b>"
              );

            /*
             * Fetch hospitals from backend.
             */
            await fetchHospitals(
              latitude,
              longitude,
              selectedRadius,
              "all",
              false
            );
          },

          (error) => {
            console.error(
              "Geolocation error:",
              error
            );

            setLocationError(
              "Location permission is required to find nearby hospitals."
            );

            setLoading(false);
          },

          {
            enableHighAccuracy: false,
            timeout: 7000,
            maximumAge: 300000,
          }
        );

        /*
         * Fix Leaflet rendering after
         * container becomes visible.
         */
        setTimeout(() => {
          if (!cancelled) {
            map.invalidateSize();
          }
        }, 300);
      } catch (error) {
        console.error(
          "Failed to initialize Leaflet:",
          error
        );

        setLocationError(
          "Unable to load the map."
        );

        setLoading(false);
      }
    };

    initializeMap();

    return () => {
      cancelled = true;

      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }

      markersRef.current = null;

      hospitalMarkersRef.current.clear();

      leafletRef.current = null;
    };

    // Map should initialize only once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /*
   * Radius filter.
   */
  const handleRadiusChange = (
    radius: number
  ) => {
    setSelectedRadius(radius);

    const location =
      userLocationRef.current;

    if (!location) {
      return;
    }

    fetchHospitals(
      location.latitude,
      location.longitude,
      radius,
      specialtyFilter,
      emergencyOnly
    );
  };

  /*
   * Specialty filter.
   */
  const handleSpecialtyChange = (
    specialty: string
  ) => {
    setSpecialtyFilter(specialty);

    const location =
      userLocationRef.current;

    if (!location) {
      return;
    }

    fetchHospitals(
      location.latitude,
      location.longitude,
      selectedRadius,
      specialty,
      emergencyOnly
    );
  };

  /*
   * Emergency filter.
   */
  const handleEmergencyChange = (
    checked: boolean
  ) => {
    setEmergencyOnly(checked);

    const location =
      userLocationRef.current;

    if (!location) {
      return;
    }

    fetchHospitals(
      location.latitude,
      location.longitude,
      selectedRadius,
      specialtyFilter,
      checked
    );
  };

  /*
   * Local text search.
   *
   * This searches hospitals already returned
   * by the backend.
   */
  const filteredHospitals =
    hospitals.filter((hospital) => {
      const searchTerm =
        search.toLowerCase().trim();

      if (!searchTerm) {
        return true;
      }

      return (
        hospital.name
          .toLowerCase()
          .includes(searchTerm) ||
        hospital.address
          .toLowerCase()
          .includes(searchTerm) ||
        hospital.city
          .toLowerCase()
          .includes(searchTerm)
      );
    });

  /*
   * Backend already sorts by distance.
   * This keeps the frontend sorted as well.
   */
  const sortedHospitals =
    [...filteredHospitals].sort(
      (a, b) =>
        (a.distance_km ?? 999999) -
        (b.distance_km ?? 999999)
    );

  /*
   * Update Leaflet markers whenever
   * hospital results change.
   */
  useEffect(() => {
    const L = leafletRef.current;

    if (
      !L ||
      !markersRef.current
    ) {
      return;
    }

    /*
     * Remove previous hospital markers.
     */
    markersRef.current.clearLayers();

    hospitalMarkersRef.current.clear();

    /*
     * Create markers for current results.
     */
    sortedHospitals.forEach(
      (hospital) => {
        const marker = L.marker([
          hospital.latitude,
          hospital.longitude,
        ]);

        const googleMapsUrl =
          `https://www.google.com/maps/dir/?api=1` +
          `&destination=${hospital.latitude},${hospital.longitude}`;

        /*
         * Popup content.
         */
        marker.bindPopup(`
          <div style="min-width:240px">

            <strong>
              ${hospital.name}
            </strong>

            ${
              hospital.distance_km !==
              undefined
                ? `
                  <p style="margin:6px 0">
                    📍 ${hospital.distance_km} km away
                  </p>
                `
                : ""
            }

            ${
              hospital.address
                ? `
                  <p style="margin:6px 0">
                    ${hospital.address}
                  </p>
                `
                : ""
            }

            ${
              hospital.specialties
                ? `
                  <p style="margin:6px 0">
                    🩺 ${hospital.specialties}
                  </p>
                `
                : ""
            }

            ${
              hospital.rating !== null &&
              hospital.rating !== undefined
                ? `
                  <p style="margin:6px 0">
                    ⭐ ${hospital.rating}
                  </p>
                `
                : ""
            }

            ${
              hospital.consultation_fee !==
                null &&
              hospital.consultation_fee !==
                undefined
                ? `
                  <p style="margin:6px 0">
                    💰 ₹${hospital.consultation_fee}
                  </p>
                `
                : ""
            }

            ${
              hospital.waiting_time !==
                null &&
              hospital.waiting_time !==
                undefined
                ? `
                  <p style="margin:6px 0">
                    ⏱️ ${hospital.waiting_time} min waiting
                  </p>
                `
                : ""
            }

            ${
              hospital.emergency_available
                ? `
                  <p style="margin:6px 0">
                    🚑 Emergency Available
                  </p>
                `
                : ""
            }

            ${
              hospital.icu_available
                ? `
                  <p style="margin:6px 0">
                    🏥 ICU Available
                  </p>
                `
                : ""
            }

            ${
              hospital.languages
                ? `
                  <p style="margin:6px 0">
                    🗣️ ${hospital.languages}
                  </p>
                `
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

        marker.addTo(
          markersRef.current!
        );

        hospitalMarkersRef.current.set(
          hospital.id,
          marker
        );
      }
    );
  }, [sortedHospitals]);

  return (
    <div className="overflow-hidden rounded-2xl border border-border/70 bg-card">

      <div className="grid lg:grid-cols-[320px_1fr]">

        {/* =========================
            LEFT PANEL
        ========================== */}
        <div className="max-h-[600px] overflow-y-auto border-r border-border">

          <div className="border-b border-border p-5">

            <h2 className="font-semibold">
              Nearby Hospitals
            </h2>

            <p className="mt-1 text-xs text-muted-foreground">
              Find hospitals around your current location
            </p>

            {/* SEARCH */}
            <div className="mt-4">

              <input
                type="text"
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value
                  )
                }
                placeholder="Search hospitals..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              />

            </div>

            {/* RADIUS */}
            <div className="mt-4">

              <p className="mb-2 text-xs font-medium">
                Search radius
              </p>

              <div className="flex gap-2">

                {[5, 10, 20].map(
                  (radius) => (
                    <button
                      key={radius}
                      type="button"
                      onClick={() =>
                        handleRadiusChange(
                          radius
                        )
                      }
                      className={`rounded-lg border px-3 py-1.5 text-xs transition ${
                        selectedRadius ===
                        radius
                          ? "border-primary bg-primary text-primary-foreground"
                          : "border-border hover:bg-muted"
                      }`}
                    >
                      {radius} km
                    </button>
                  )
                )}

              </div>
            </div>

            {/* SPECIALTY */}
            <div className="mt-4">

              <label className="mb-2 block text-xs font-medium">
                Specialty
              </label>

              <select
                value={specialtyFilter}
                onChange={(event) =>
                  handleSpecialtyChange(
                    event.target.value
                  )
                }
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
              >

                <option value="all">
                  All Specialties
                </option>

                <option value="cardiology">
                  Cardiology
                </option>

                <option value="orthopedic">
                  Orthopedics
                </option>

                <option value="general medicine">
                  General Medicine
                </option>

                <option value="pediatrics">
                  Pediatrics
                </option>

                <option value="gynecology">
                  Gynecology
                </option>

                <option value="neurology">
                  Neurology
                </option>

                <option value="oncology">
                  Oncology
                </option>

                <option value="pulmonology">
                  Pulmonology
                </option>

              </select>

            </div>

            {/* EMERGENCY */}
            <div className="mt-4">

              <label className="flex items-center gap-2 text-sm">

                <input
                  type="checkbox"
                  checked={emergencyOnly}
                  onChange={(event) =>
                    handleEmergencyChange(
                      event.target.checked
                    )
                  }
                  className="h-4 w-4 rounded border-border"
                />

                <span>
                  Emergency available
                </span>

              </label>

            </div>

            {/* LOADING */}
            {loading && (
              <p className="mt-3 text-xs text-muted-foreground">
                Finding nearby hospitals...
              </p>
            )}

            {/* ERROR */}
            {locationError && (
              <p className="mt-3 text-xs text-destructive">
                {locationError}
              </p>
            )}

          </div>

          {/* =========================
              HOSPITAL LIST
          ========================== */}
          <div className="p-3">

            {!loading &&
              sortedHospitals.length ===
                0 &&
              !locationError && (
                <p className="p-4 text-sm text-muted-foreground">
                  No hospitals found within{" "}
                  {selectedRadius} km.
                </p>
              )}

            {sortedHospitals.map(
              (hospital) => (
                <button
                  key={hospital.id}
                  type="button"
                  className="mb-2 w-full rounded-xl border border-border/70 p-4 text-left transition hover:bg-muted"
                  onClick={() => {
                    const map =
                      mapRef.current;

                    const marker =
                      hospitalMarkersRef.current.get(
                        hospital.id
                      );

                    if (
                      map &&
                      marker
                    ) {
                      map.setView(
                        [
                          hospital.latitude,
                          hospital.longitude,
                        ],
                        16
                      );

                      marker.openPopup();
                    }
                  }}
                >

                  {/* NAME */}
                  <div className="flex items-start justify-between gap-2">

                    <p className="font-medium">
                      {hospital.name}
                    </p>

                    <span className="shrink-0 rounded-full bg-primary/10 px-2 py-1 text-[10px] font-medium text-primary">
                      MedTour
                    </span>

                  </div>

                  {/* ADDRESS */}
                  {hospital.address && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {hospital.address}
                    </p>
                  )}

                  {/* DISTANCE */}
                  {hospital.distance_km !==
                    undefined && (
                    <p className="mt-2 text-xs text-primary">
                      📍{" "}
                      {hospital.distance_km.toFixed(
                        1
                      )}{" "}
                      km away
                    </p>
                  )}

                  {/* SPECIALTIES */}
                  {hospital.specialties && (
                    <p className="mt-2 text-xs">
                      🩺{" "}
                      {hospital.specialties}
                    </p>
                  )}

                  {/* RATING / COST / WAIT */}
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">

                    {hospital.rating !==
                      null &&
                      hospital.rating !==
                        undefined && (
                        <span>
                          ⭐{" "}
                          {hospital.rating}
                        </span>
                      )}

                    {hospital.consultation_fee !==
                      null &&
                      hospital.consultation_fee !==
                        undefined && (
                        <span>
                          💰 ₹
                          {
                            hospital.consultation_fee
                          }
                        </span>
                      )}

                    {hospital.waiting_time !==
                      null &&
                      hospital.waiting_time !==
                        undefined && (
                        <span>
                          ⏱️{" "}
                          {
                            hospital.waiting_time
                          }{" "}
                          min
                        </span>
                      )}

                  </div>

                  {/* EMERGENCY */}
                  {hospital.emergency_available && (
                    <p className="mt-2 text-xs font-medium text-green-600">
                      🚑 Emergency Available
                    </p>
                  )}

                  {/* ICU */}
                  {hospital.icu_available && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      🏥 ICU Available
                    </p>
                  )}

                  {/* LANGUAGES */}
                  {hospital.languages && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      🗣️{" "}
                      {hospital.languages}
                    </p>
                  )}

                  {/* VIEW ON MAP */}
                  <div className="mt-2">
                    <span className="text-xs text-primary">
                      View on map
                    </span>
                  </div>

                </button>
              )
            )}

          </div>

        </div>

        {/* =========================
            MAP
        ========================== */}
        <div className="relative min-h-[500px]">

          <div
            ref={mapContainerRef}
            className="h-[600px] w-full"
          />

          {/* RESULT COUNT */}
          <div className="absolute left-4 top-4 z-[1000] rounded-lg bg-background/95 px-4 py-2 shadow">

            <p className="text-xs font-medium">

              {loading
                ? "Finding nearby hospitals..."
                : `${sortedHospitals.length} hospitals found`}

            </p>

          </div>

        </div>

      </div>

    </div>
  );
}