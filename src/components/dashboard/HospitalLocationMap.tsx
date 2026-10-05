import { useEffect, useRef } from "react";
import "leaflet/dist/leaflet.css";

type HospitalLocationMapProps = {
  latitude: number;
  longitude: number;
  hospitalName: string;
  city?: string | null;
  state?: string;
};

/* Escape text before injecting into popup HTML */
const esc = (value: string) =>
  value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

export function HospitalLocationMap({
  latitude,
  longitude,
  hospitalName,
  city,
  state,
}: HospitalLocationMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<any>(null);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    let cancelled = false;

    const initMap = async () => {
      const L = await import("leaflet");

      if (cancelled || !mapContainerRef.current) return;

      const map = L.map(mapContainerRef.current, {
        center: [latitude, longitude],
        zoom: 16,
        zoomControl: true,
        attributionControl: true,
        scrollWheelZoom: false,
        bounceAtZoomLimits: false,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);

      const locationLine = Array.from(
        new Set(
          [city, state]
            .filter((part): part is string => !!part && part.trim().length > 0)
        )
      ).join(", ");

      const popupContent = `
        <div style="font-size:14px">
          <strong>${esc(hospitalName)}</strong>
          ${
            locationLine
              ? `<div style="margin-top:4px;color:#555;font-size:12px">${esc(
                  locationLine
                )}</div>`
              : ""
          }
        </div>
      `;

      /* Inline SVG pin — no external image assets, no bundler URL issues */
      const pinIcon = L.divIcon({
        className: "",
        iconSize: [30, 42],
        iconAnchor: [15, 42],
        popupAnchor: [0, -38],
        html: `
          <svg width="30" height="42" viewBox="0 0 30 42" xmlns="http://www.w3.org/2000/svg">
            <path d="M15 0C6.7 0 0 6.7 0 15c0 10.5 13.1 25.4 13.7 26a1.5 1.5 0 0 0 2.6 0C16.9 40.4 30 25.5 30 15 30 6.7 23.3 0 15 0z"
                  fill="#1d4ed8"/>
            <circle cx="15" cy="15" r="5.5" fill="#ffffff"/>
          </svg>
        `,
      });

      L.marker([latitude, longitude], {
        icon: pinIcon,
        title: hospitalName,
        alt: hospitalName,
      })
        .addTo(map)
        .bindPopup(popupContent, { autoClose: true, closeButton: false })
        .openPopup();

      mapRef.current = map;

      // Invalidate size after a brief delay to ensure tile container is painted
      setTimeout(() => {
        map.invalidateSize();
      }, 200);
    };

    initMap();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, [latitude, longitude, hospitalName, city, state]);

  return (
    <div
      ref={mapContainerRef}
      className="h-full w-full"
      style={{ minHeight: "200px" }}
      aria-label={`Map showing location of ${hospitalName}`}
    />
  );
}
