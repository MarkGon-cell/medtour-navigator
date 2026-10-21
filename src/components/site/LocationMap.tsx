import { useEffect, useRef, useState } from "react";
import type { CircleMarker, Map, Polyline } from "leaflet";
import "leaflet/dist/leaflet.css";

export type DispatchMode = "uber" | "ola" | "ambulance";

export type DispatchTarget = {
  latitude: number;
  longitude: number;
  name: string;
};

type LocationMapProps = {
  /** Your position. The map centres here and stays centred. */
  latitude: number;
  longitude: number;
  /** Set once a ride or ambulance has been asked for. */
  target?: DispatchTarget | null;
  mode?: DispatchMode;
  /** Shown under the header, e.g. "Vasai Road, Vasai-Virar". */
  caption?: string;
  /**
   * Classes for the map viewport itself. Defaults to the compact mobile
   * height; pass a taller class on desktop so the map tracks the column
   * beside it instead of leaving a dead gap underneath.
   */
  viewportClassName?: string;
};

const MODE_STYLE: Record<DispatchMode, { label: string; color: string }> = {
  uber: { label: "Uber pickup", color: "#000000" },
  ola: { label: "Ola pickup", color: "#1E293B" },
  ambulance: { label: "Ambulance route", color: "#D92D20" },
};

/**
 * The map under the GPS readout on the home page.
 *
 * Always shows where you are. Once Uber / Ola / the ambulance has been
 * requested it also drops the destination and the line between you two.
 *
 * Leaflet is imported dynamically because it touches `window` at module
 * scope and would break SSR. Points are circleMarkers, not the default pin,
 * because those pin PNGs 404 under a bundler unless they're copied across.
 */
export function LocationMap({
  latitude,
  longitude,
  target,
  mode,
  caption,
  viewportClassName = "h-52 w-full sm:h-64",
}: LocationMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const meRef = useRef<CircleMarker | null>(null);
  const targetRef = useRef<CircleMarker | null>(null);
  const lineRef = useRef<Polyline | null>(null);
  // The map only ever gets built once; later prop changes mutate it in place.
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const init = async () => {
      if (!containerRef.current || mapRef.current) return;

      try {
        const L = await import("leaflet");
        if (cancelled || !containerRef.current) return;

        const map = L.map(containerRef.current, {
          zoomControl: false,
          scrollWheelZoom: false,
          attributionControl: true,
        }).setView([latitude, longitude], 14);

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(map);

        mapRef.current = map;
        setMapReady(true);

        // The card is inserted after mount, so tiles need a nudge.
        setTimeout(() => {
          if (!cancelled) map.invalidateSize();
        }, 250);
      } catch (error) {
        console.error("Failed to initialise location map:", error);
      }
    };

    init();

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      meRef.current = null;
      targetRef.current = null;
      lineRef.current = null;
    };
    // Deliberately mount-once: position and target are applied below.
  }, []);

  // Keep the "you are here" dot on the current GPS fix, and redraw the
  // dispatch overlay whenever a ride or ambulance is asked for.
  useEffect(() => {
    if (!mapReady || !mapRef.current) return;
    let cancelled = false;

    (async () => {
      const L = await import("leaflet");
      const map = mapRef.current;
      if (cancelled || !map) return;

      const here: [number, number] = [latitude, longitude];

      if (!meRef.current) {
        meRef.current = L.circleMarker(here, {
          radius: 9,
          color: "#0f766e",
          fillColor: "#14b8a6",
          fillOpacity: 0.95,
          weight: 3,
        })
          .addTo(map)
          .bindPopup("<b>You are here</b>");
      } else {
        meRef.current.setLatLng(here);
      }

      // Previous dispatch overlay, if any.
      if (targetRef.current) {
        targetRef.current.remove();
        targetRef.current = null;
      }
      if (lineRef.current) {
        lineRef.current.remove();
        lineRef.current = null;
      }

      if (target && mode) {
        const style = MODE_STYLE[mode];
        const dest: [number, number] = [target.latitude, target.longitude];

        targetRef.current = L.circleMarker(dest, {
          radius: 9,
          color: style.color,
          fillColor: style.color,
          fillOpacity: 0.9,
          weight: 3,
        })
          .addTo(map)
          .bindPopup(`<b>${target.name}</b>`);

        // Straight line, not a road-accurate route -- it's a visual link.
        lineRef.current = L.polyline([here, dest], {
          color: style.color,
          weight: 4,
          opacity: 0.75,
          dashArray: "8 8",
        }).addTo(map);

        map.fitBounds(L.latLngBounds([here, dest]).pad(0.25));
      } else {
        // No dispatch live: stay with the user.
        map.setView(here, map.getZoom() < 12 ? 14 : map.getZoom());
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [mapReady, latitude, longitude, target, mode]);

  const style = mode ? MODE_STYLE[mode] : null;

  return (
    // `isolate` is the whole fix. Leaflet paints its tiles, markers and
    // popups at z-index 200-1000; without a stacking context of our own
    // those values escape into the page and paint over the z-40 Uber/OLA
    // bar and the MobileNav. Isolating here traps them, so the map sits
    // under the floating bars no matter what Leaflet asks for.
    <div className="relative isolate z-0 overflow-hidden rounded-2xl border border-border/70 bg-card shadow-xs lg:flex lg:flex-col lg:h-full lg:min-h-0">
      {style && target && (
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <span
            className="text-[11px] font-extrabold uppercase tracking-wider"
            style={{ color: style.color }}
          >
            {style.label}
          </span>
          <span className="truncate text-[11px] font-semibold text-muted-foreground">
            → {target.name}
          </span>
        </div>
      )}

      {/* On desktop the viewport flexes to fill the column so the map and the
          stack beside it share a bottom edge; below lg it keeps its fixed
          mobile heights. `min-h-0` lets it shrink inside the flex column. */}
      <div ref={containerRef} className={`${viewportClassName} lg:flex-1 lg:h-auto lg:min-h-0`} />

      {caption && (
        <div className="border-t border-border px-3 py-2 text-[11px] font-semibold text-muted-foreground truncate shrink-0">
          {caption}
        </div>
      )}
    </div>
  );
}
