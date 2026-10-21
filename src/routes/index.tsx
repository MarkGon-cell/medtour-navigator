import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { MobileNav } from "@/components/site/MobileNav.tsx";
import { QuickMedicalIdModal } from "@/components/site/QuickMedicalIdModal";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FiPhone, FiCopy, FiMapPin, FiNavigation } from "react-icons/fi";
import { FaCar, FaLocationArrow } from "react-icons/fa";
import { toast } from "sonner";
import { useCallback, useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import {
  describeGeolocationFailure,
  isPosition,
  readPosition,
  type GeolocationOutcome,
} from "@/lib/geolocation";
import { LocationMap, type DispatchMode } from "@/components/site/LocationMap";
import { RefreshLocationIcon } from "@/components/site/RefreshLocationIcon";
import { PageHeader } from "@/components/site/PageHeader";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MedTour — Emergency Gateway" },
      { name: "description", content: "Instant emergency toolkit for travellers." },
    ],
  }),
  component: Landing,
});

const HOME_SESSION_KEY = "medtour_tab_home_state";

// Read the Home tab state saved by the previous visit. Called AFTER mount --
// never during render -- see the restore effect below.
function readSavedHomeState() {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(HOME_SESSION_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

function Landing() {
  const navigate = useNavigate();

  // Defaults must match what the server renders. sessionStorage is read in an
  // effect further down: the server has no sessionStorage, so any value read
  // here would make the first client render differ from the server HTML and
  // React would discard the hydrated subtree with a hydration mismatch.
  const [addressString, setAddressString] = useState<string>("Locating GPS position...");
  const [cityStateString, setCityStateString] = useState<string>("Fetching coordinates...");
  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [isMedicalIdOpen, setIsMedicalIdOpen] = useState(false);
  const [isDriverCardOpen, setIsDriverCardOpen] = useState(false);

  // The card walks OUTWARD from the user: try 1 km, then 3, 5, 10, 20 and
  // stop at the first radius that actually returns a facility.
  const ER_RADIUS_LADDER_KM = [1, 3, 5, 10, 20];

  type NearestHospital = {
    name: string;
    address: string;
    distanceKm: number;
    phone: string;
    latitude: number;
    longitude: number;
    searchedRadiusKm: number;
    isGeneralOrMultispeciality?: boolean;
  };

  const [nearestHospital, setNearestHospital] = useState<NearestHospital | null>(null);
  const [isFindingEr, setIsFindingEr] = useState(false);
  const [erStatus, setErStatus] = useState<"idle" | "searching" | "found" | "empty" | "error">(
    "idle",
  );

  // Refreshing GPS: the blue pin in the Uber/OLA bar re-runs this.
  const [isRefreshingLocation, setIsRefreshingLocation] = useState(false);
  const erRequestSeq = useRef(0);

  // Restore the previous visit on mount -- AFTER the server has had its say.
  // This runs before the persistence effect below (effects fire in
  // declaration order), so it reads sessionStorage before that effect can
  // overwrite it with the defaults from this render.
  const didRestoreHome = useRef(false);
  useEffect(() => {
    if (didRestoreHome.current) return;
    didRestoreHome.current = true;

    const saved = readSavedHomeState();
    if (!saved) return;

    if (saved.addressString) setAddressString(saved.addressString);
    if (saved.cityStateString) setCityStateString(saved.cityStateString);
    if (saved.userLocation) setUserLocation(saved.userLocation);
    if (saved.nearestHospital) setNearestHospital(saved.nearestHospital);
    if (saved.erStatus) setErStatus(saved.erStatus);
  }, []);

  // Persist Home tab state
  useEffect(() => {
    try {
      const stateToSave = {
        addressString,
        cityStateString,
        userLocation,
        nearestHospital,
        erStatus,
      };
      sessionStorage.setItem(HOME_SESSION_KEY, JSON.stringify(stateToSave));
    } catch {}
  }, [addressString, cityStateString, userLocation, nearestHospital, erStatus]);

  const fetchNearestEr = useCallback(async (lat: number, lng: number) => {
    const seq = ++erRequestSeq.current;
    setIsFindingEr(true);
    setErStatus("searching");

    try {
      let fallbackCandidate: NearestHospital | null = null;

      for (const radiusKm of ER_RADIUS_LADDER_KM) {
        if (seq !== erRequestSeq.current) return; // superseded

        const res = await api.get("/hospitals/nearby", {
          params: { latitude: lat, longitude: lng, radius_km: radiusKm, sort: "emergency", limit: 5 },
        });

        const rows = Array.isArray(res.data) ? res.data : [];
        if (rows.length > 0) {
          // Check if there is an authoritative General or Multi-Speciality hospital at this radius
          const bestMatch = rows.find((r: any) => r.is_general_or_multispeciality) || rows[0];

          const mapped: NearestHospital = {
            name: bestMatch.name,
            address: bestMatch.address || [bestMatch.city, bestMatch.state].filter(Boolean).join(", ") || "Address on map",
            distanceKm: bestMatch.distance_km,
            phone: bestMatch.phone || bestMatch.emergency_phone || bestMatch.ambulance_phone || "",
            latitude: bestMatch.latitude,
            longitude: bestMatch.longitude,
            searchedRadiusKm: radiusKm,
            isGeneralOrMultispeciality: Boolean(bestMatch.is_general_or_multispeciality),
          };

          if (mapped.isGeneralOrMultispeciality) {
            setNearestHospital(mapped);
            setErStatus("found");
            return;
          }

          if (!fallbackCandidate) {
            fallbackCandidate = mapped;
          }
        }
      }

      if (fallbackCandidate) {
        setNearestHospital(fallbackCandidate);
        setErStatus("found");
        return;
      }

      setNearestHospital(null);
      setErStatus("empty");
    } catch {
      if (seq !== erRequestSeq.current) return;
      setErStatus("error");
    } finally {
      if (seq === erRequestSeq.current) setIsFindingEr(false);
    }
  }, []);

  // Which service was asked for. `dispatch` below drives the map overlay.
  const [isDispatching, setIsDispatching] = useState(false);
  const [sosDestination, setSosDestination] = useState<{
    name: string;
    address?: string;
    city?: string;
    phone?: string;
    latitude: number;
    longitude: number;
    distance_km: number;
    eta_minutes: number;
    google_maps_route: string;
  } | null>(null);

  // Set the moment a ride or ambulance is asked for. Drives the dispatch map
  // below the GPS readout: you, the destination, and the line between.
  const [dispatch, setDispatch] = useState<{
    mode: DispatchMode;
    target: { latitude: number; longitude: number; name: string };
  } | null>(null);

  // Fetch GPS once on load. `loadMyLocation` is also what the blue pin calls
  // to re-locate on demand.
  const loadMyLocation = useCallback(async () => {
    if (!navigator.geolocation) {
      setAddressString("Bandra Kurla Complex, Mumbai");
      setCityStateString("Maharashtra • 19.0760° N, 72.8777° E");
      setUserLocation({ lat: 19.0760, lng: 72.8777 });
      return;
    }

    setIsRefreshingLocation(true);

    // Failure path: releases the refreshing flag so the pin can never be left
    // spinning, and says WHY location is unavailable. Every branch now
    // explains itself -- codes 2 (no fix: Location toggle off, no GPS in
    // sight) and 3 (timeout) used to fall back in silence, which on a phone
    // meant the page showed the default Bandra address as though it were the
    // patient's own position.
    const fallBackToSavedLocation = (reason?: string) => {
      console.warn("[geolocation] using the default position instead:", reason ?? "no reason");
      setAddressString("Bandra Kurla Complex Rd, Bandra East");
      setCityStateString("Mumbai, Maharashtra • 19.0760° N, 72.8777° E");
      setUserLocation({ lat: 19.0760, lng: 72.8777 });
      setErStatus("error");
      setIsRefreshingLocation(false);
      if (reason) toast.error(reason);
    };

    // Two-stage read -- cheap cache/Wi-Fi fix first, then a longer GPS wait --
    // so a phone indoors gets a real chance to answer. See lib/geolocation.
    let outcome: GeolocationOutcome;
    try {
      outcome = await readPosition();
    } catch {
      fallBackToSavedLocation("Couldn't read your location. Tap the blue pin to try again.");
      return;
    }

    try {
      if (!isPosition(outcome)) {
        // Chrome's own reason travels on `message` ("No location was
        // available.", "The Last Position Provider Has Been Unbound.", …).
        // It is the one clue that separates a blocked permission from a
        // device with no location source at all, so never swallow it.
        console.warn(
          "[geolocation] readPosition failed: code=%s message=%o",
          outcome?.code,
          outcome?.message,
        );
        fallBackToSavedLocation(describeGeolocationFailure(outcome));
        return;
      }
      const pos = outcome;

      // Some implementations report success without carrying a position
      // (seen as `pos.coords is undefined`). Treat that as a failure instead
      // of throwing -- a throw here used to skip setIsRefreshingLocation
      // entirely and freeze the pin forever -- but log the raw payload so the
      // console identifies the culprit.
      const lat = pos?.coords?.latitude;
      const lng = pos?.coords?.longitude;
      if (
        typeof lat !== "number" ||
        typeof lng !== "number" ||
        Number.isNaN(lat) ||
        Number.isNaN(lng)
      ) {
        console.warn("[geolocation] unusable position payload:", pos);
        fallBackToSavedLocation(
          typeof window !== "undefined" && !window.isSecureContext
            ? // Firefox and Chrome both withhold coordinates on non-secure
              // origins -- 192.168.x.x over plain HTTP is not one, and
              // neither browser can be configured to allow it.
              "This address isn't secure, so the browser won't share your coordinates. Use https:// or localhost."
            : "Your browser returned a position without coordinates. Tap the blue pin to try again.",
        );
        return;
      }
      setUserLocation({ lat, lng });

      // Send the coordinates to the backend FIRST. Reverse geocoding
      // below is cosmetic (it only fills in a street name) and runs on a
      // third-party host with no timeout of its own -- awaiting it before
      // the search meant one stalled Nominatim request kept the patient's
      // location from ever reaching /hospitals/nearby.
      const erLookup = fetchNearestEr(lat, lng);

      // Reverse geocode live coordinates using Nominatim API (best effort,
      // 5s cap, never allowed to hold up the search above).
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}&zoom=18&addressdetails=1`,
          {
            headers: { "Accept-Language": "en" },
            signal: typeof AbortSignal !== "undefined" && "timeout" in AbortSignal
              ? AbortSignal.timeout(5000)
              : undefined,
          }
        );
        const data = await res.json();
        if (data && data.address) {
          const road = data.address.road || data.address.suburb || data.address.neighbourhood || data.address.residential || data.address.village || "Current Location";
          const city = data.address.city || data.address.town || data.address.city_district || data.address.suburb || data.address.county || "Maharashtra";
          const state = data.address.state || "Maharashtra";
          setAddressString(`${road}`);
          setCityStateString(`${city}, ${state} • ${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`);
        } else {
          setAddressString(`GPS Position (${lat.toFixed(4)}°, ${lng.toFixed(4)}°)`);
          setCityStateString(`${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`);
        }
      } catch {
        setAddressString(`GPS Position (${lat.toFixed(4)}°, ${lng.toFixed(4)}°)`);
        setCityStateString(`${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`);
      }

      // Walk the radius ladder outward until an ER turns up.
      await erLookup;
    } catch {
      setErStatus("error");
    } finally {
      setIsRefreshingLocation(false);
    }
  }, [fetchNearestEr]);

  useEffect(() => {
    loadMyLocation();
  }, [loadMyLocation]);

  // Blue pin in the Uber/OLA bar: re-read GPS and re-run the ER ladder.
  const handleRefreshLocation = () => {
    if (isRefreshingLocation) return;
    toast.info("Refreshing your location…");
    loadMyLocation();
  };

  const copyAddressToClipboard = () => {
    const fullText = `${addressString}, ${cityStateString}`;
    navigator.clipboard.writeText(fullText);
    toast.success("Address & coordinates copied!");
  };

  // SOS does TWO things at once:
  //   1. opens tel:112 — the real emergency channel (works offline);
  //   2. POSTs /emergency/sos — backend curates the nearest emergency ER,
  //      computes route + ETA from the user's GPS, and returns a dispatch
  //      packet so the caller knows where to take the patient.
  const handleSOS = () => {
    const lat = userLocation?.lat ?? 19.0760;
    const lng = userLocation?.lng ?? 72.8777;

    // 1. Dial emergency services immediately — never wait on the network.
    window.location.href = "tel:112";

    // 2. Fire the dispatch-packet request in parallel.
    setIsDispatching(true);
    setSosDestination(null);
    api
      .post("/emergency/sos", {
        latitude: lat,
        longitude: lng,
        address: `${addressString}, ${cityStateString}`,
        message: "Emergency SOS triggered from MedTour home",
        contact_emergency_services: true,
      })
      .then((res: any) => {
        if (res.data?.destination) {
          const d = res.data.destination;
          setSosDestination(d);
          setDispatch({
            mode: "ambulance",
            target: { latitude: d.latitude, longitude: d.longitude, name: d.name },
          });
          toast.success(`🚑 Nearest ER: ${d.name}`, {
            duration: 6000,
          });
        } else {
          toast.info("No ER found nearby — call 112 for dispatch.", {
            duration: 6000,
          });
        }
      })
      .catch(() => {
        toast.error("Couldn't reach dispatch — call 112 directly.", {
          duration: 6000,
        });
      })
      .finally(() => setIsDispatching(false));
  };

  const triggerRideHail = (service: "uber" | "ola") => {
    const lat = userLocation?.lat || 19.0760;
    const lng = userLocation?.lng || 72.8777;

    // The destination is always the nearest ER the card resolved. Without a
    // resolved hospital there is nothing meaningful to hail a ride to.
    if (!nearestHospital) {
      toast.error("No ER resolved yet — let the search finish, then retry.");
      return;
    }

    setDispatch({
      mode: service,
      target: {
        latitude: nearestHospital.latitude,
        longitude: nearestHospital.longitude,
        name: nearestHospital.name,
      },
    });

    if (service === "uber") {
      const uberUri = `uber://?action=setPickup&pickup=my_location&dropoff[latitude]=${nearestHospital.latitude}&dropoff[longitude]=${nearestHospital.longitude}&dropoff[nickname]=${encodeURIComponent(nearestHospital.name)}`;
      const uberWeb = `https://m.uber.com/ul/?action=setPickup&pickup=my_location&dropoff[latitude]=${nearestHospital.latitude}&dropoff[longitude]=${nearestHospital.longitude}`;
      window.location.href = uberUri;
      setTimeout(() => { window.location.href = uberWeb; }, 1000);
    } else {
      const olaWeb = `https://book.olacabs.com/?lat=${lat}&lng=${lng}&drop_lat=${nearestHospital.latitude}&drop_lng=${nearestHospital.longitude}`;
      window.location.href = olaWeb;
    }
  };

  // Extra bottom clearance: the Uber/OLA bar and the MobileNav float above
  // the page, and the map now sits last in the stack. pb-44 alone left the
  // map's lower edge under the Uber/OLA bar.
  return (
    <div className="min-h-screen bg-background pb-40 font-sans">
      {/* Top Center Minimal MedTour Brand (Takes user to /landing) */}
      <header className="w-full pt-4 pb-2 flex items-center justify-center">
        <button
          onClick={() => navigate({ to: "/landing" })}
          className="group inline-flex items-center gap-2 px-4 py-1.5 rounded-full hover:bg-muted/60 transition-all cursor-pointer focus:outline-none"
          aria-label="MedTour Landing Page"
        >
          <span className="text-xl font-black tracking-tight text-foreground group-hover:opacity-85 transition-opacity">
            MedTour
          </span>
        </button>
      </header>

      <main className="max-w-3xl lg:max-w-7xl xl:max-w-[90rem] mx-auto px-4 py-2 space-y-4 lg:grid lg:grid-cols-12 lg:gap-6 lg:items-stretch lg:space-y-0 lg:min-h-[calc(100vh-15rem)]">
        
        {/* LEFT COLUMN (mobile stack / desktop col-span-5).
            Desktop uses the grid's default `align-items: stretch`, so this
            column and the map are always the same height and share a bottom
            edge — see the min-h on <main> for where that edge lands. */}
        <div className="space-y-4 lg:col-span-5 lg:flex lg:flex-col">
        {/* ZONE 1: NEAREST HOSPITAL & GET DIRECTIONS BUTTON */}
        <div className="p-4 sm:p-5 rounded-3xl border-2 border-primary/40 bg-card space-y-3 sm:space-y-4 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
            <div className="min-w-0 flex-1">
              <span className="px-2.5 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] sm:text-xs font-bold inline-block mb-1">
                NEAREST 24/7 ER & URGENT CARE
              </span>
              <h2 className="text-base sm:text-xl font-extrabold text-foreground leading-snug break-words">
                {erStatus === "searching"
                  ? "Searching near you…"
                  : nearestHospital?.name ?? "No ER found nearby"}
              </h2>
              <p className="text-xs font-medium text-muted-foreground mt-1 flex items-start gap-1.5 leading-normal">
                <FiMapPin className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                <span className="break-words line-clamp-2">
                  {erStatus === "searching"
                    ? "Checking 1 km, then widening outward…"
                    : nearestHospital?.address ?? "Try refreshing your location."}
                </span>
              </p>
            </div>
            {nearestHospital && erStatus === "found" && (
              <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 shrink-0 pt-0.5 sm:pt-0">
                {nearestHospital.isGeneralOrMultispeciality && (
                  <span className="text-[10px] sm:text-xs font-extrabold px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                    General / Multi-Speciality
                  </span>
                )}
                <span className="text-[10px] sm:text-xs font-extrabold px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-primary/15 text-primary">
                  {nearestHospital.distanceKm} km away
                </span>
                <span className="text-[10px] sm:text-xs font-extrabold px-2 py-0.5 sm:px-2.5 sm:py-1 rounded-full bg-muted text-muted-foreground">
                  Within {nearestHospital.searchedRadiusKm} km
                </span>
              </div>
            )}
          </div>

          <div className="p-2.5 sm:p-3 rounded-2xl bg-muted/40 border border-border/60 text-xs text-muted-foreground font-medium flex items-center justify-between gap-2">
            <span className="truncate text-[11px] sm:text-xs">
              {erStatus === "searching"
                ? "Locating the closest emergency room…"
                : erStatus === "empty"
                ? "No ER listed within 20 km of you"
                : erStatus === "error"
                ? "Location unavailable — tap the pin to retry"
                : "Nearest facility in the hospital directory"}
            </span>
            {nearestHospital?.phone && (
              <a
                href={`tel:${nearestHospital.phone}`}
                className="text-xs font-extrabold text-primary hover:underline flex items-center gap-1 shrink-0 whitespace-nowrap"
              >
                <FiPhone className="h-3.5 w-3.5" /> Call ER
              </a>
            )}
          </div>

          {/* GET DIRECTIONS BUTTON (PROMINENT BELOW NEAREST HOSPITAL) */}
          <a
            href={
              nearestHospital
                ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${nearestHospital.name} ${nearestHospital.address}`)}`
                : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${addressString} ${cityStateString}`)}`
            }
            target="_blank"
            rel="noopener noreferrer"
            className="w-full h-11 sm:h-13 rounded-2xl bg-primary text-primary-foreground font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-sm hover:opacity-90 transition-opacity"
          >
            <FaLocationArrow className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            <span>Get Directions (Google Maps)</span>
          </a>
        </div>

        {/* ZONE 2: DRIVER CARD FLASHCARD BANNER (ABOVE CALL 112) */}
        <Button
          onClick={() => setIsDriverCardOpen(true)}
          className="w-full min-h-[3rem] sm:min-h-[3.5rem] py-2 px-3 rounded-2xl bg-foreground text-background hover:opacity-95 font-extrabold text-xs sm:text-base flex items-center justify-center gap-2 shadow-md leading-tight text-center whitespace-normal"
        >
          <FaCar className="h-4 w-4 sm:h-5 sm:w-5 shrink-0" />
          <span>Show Driver Card (EN / HI / MR)</span>
        </Button>

        {/* ZONE 3: EMERGENCY CALL 112 BUTTON (BELOW DRIVER CARD) */}
        <button
          onClick={handleSOS}
          disabled={isDispatching}
          className="w-full h-12 sm:h-14 rounded-2xl bg-[#D92D20] hover:bg-[#b82418] active:scale-[0.98] disabled:opacity-80 text-white font-extrabold text-sm sm:text-base flex items-center justify-center gap-2 shadow-md transition-all"
        >
          <FiPhone className="h-4 w-4 sm:h-5 sm:w-5 animate-pulse" />
          <span>
            {isDispatching ? "Dispatching 112 + locating ER…" : "Call Emergency Services 112 & Dispatch"}
          </span>
        </button>

        {/* SOS DISPATCH PACKET CARD — nearest ER routed from user GPS */}
        {sosDestination && (
          <div className="p-4 rounded-3xl border-2 border-[#D92D20]/40 bg-[#D92D20]/5 space-y-3 animate-in fade-in duration-300">
            <div className="flex items-center gap-2 text-xs font-extrabold text-[#D92D20] uppercase tracking-wider">
              <FiNavigation className="h-4 w-4" />
              <span>Ambulance Destination Routed</span>
            </div>
            <h3 className="text-base sm:text-lg font-extrabold text-foreground leading-snug">
              {sosDestination.name}
            </h3>
            {sosDestination.address && (
              <p className="text-xs font-medium text-muted-foreground flex items-start gap-1.5">
                <FiMapPin className="h-3.5 w-3.5 text-[#D92D20] shrink-0 mt-0.5" />
                <span>{sosDestination.address}{sosDestination.city ? `, ${sosDestination.city}` : ""}</span>
              </p>
            )}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-[#D92D20]/15 text-[#D92D20]">
                {sosDestination.distance_km} km away
              </span>
              <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-600">
                ETA ~{sosDestination.eta_minutes} min
              </span>
            </div>
            <div className="flex items-center gap-2">
              {sosDestination.phone && (
                <a
                  href={`tel:${sosDestination.phone}`}
                  className="flex-1 h-11 rounded-2xl bg-foreground text-background font-extrabold text-xs flex items-center justify-center gap-1.5"
                >
                  <FiPhone className="h-3.5 w-3.5" /> Call ER
                </a>
              )}
              <a
                href={sosDestination.google_maps_route}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 h-11 rounded-2xl bg-[#D92D20] text-white font-extrabold text-xs flex items-center justify-center gap-1.5"
              >
                <FaLocationArrow className="h-3.5 w-3.5" /> Route Ambulance
              </a>
            </div>
          </div>
        )}

        {/* Fills the desktop slack so the GPS card sits on the same bottom
            edge as the map instead of the column ending in dead space.
            Hidden on mobile where the stack just flows. */}
        <div className="hidden lg:block flex-1" aria-hidden="true" />

        {/* MIDDLE ZONE: LIVE GPS LOCATION READOUT (tap to re-locate) */}
        <div
          onClick={handleRefreshLocation}
          className="p-3.5 sm:p-4 rounded-2xl border border-border bg-card/60 flex items-center justify-between gap-2.5 shadow-xs cursor-pointer hover:bg-card transition-colors"
        >
          <div className="space-y-0.5 min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[10px] sm:text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
              <FiMapPin className="h-3.5 w-3.5 text-primary shrink-0" /> Current GPS Position
              {isRefreshingLocation && <span className="animate-pulse">• updating…</span>}
            </div>
            <h3 className="text-xs sm:text-sm font-extrabold text-foreground truncate">
              {addressString}
            </h3>
            <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
              {cityStateString}
            </p>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              copyAddressToClipboard();
            }}
            className="px-2.5 py-1.5 sm:px-3 sm:py-2 rounded-xl border border-border bg-background hover:bg-muted text-[11px] sm:text-xs font-extrabold flex items-center gap-1 shrink-0 transition-colors"
          >
            <FiCopy className="h-3.5 w-3.5" /> Copy
          </button>
        </div>
        </div>

        {/* RIGHT COLUMN (desktop only): LOCATION MAP — mobile renders it below in the same stack.
            On desktop the map now fills the column height instead of sitting as a
            short 16rem strip with a dead gap under it. */}
        <div className="lg:col-span-7 lg:flex lg:flex-col lg:min-h-0">
          {userLocation && (
            <LocationMap
              latitude={userLocation.lat}
              longitude={userLocation.lng}
              target={dispatch?.target ?? null}
              mode={dispatch?.mode}
              caption={`${addressString} • ${cityStateString}`}
              viewportClassName="h-42 w-full sm:h-52 lg:h-[calc(100vh-11rem)]"
            />
          )}
        </div>

      </main>

      {/* FLOATING NESTED SUB-NAVBAR FOR HOME: QUICK UBER, OLA, AND CURRENT LOCATION BUTTONS */}
      <div className="fixed bottom-[5.75rem] left-0 right-0 z-40 flex justify-center px-3 sm:px-4 pointer-events-none pb-[env(safe-area-inset-bottom)] animate-in fade-in slide-in-from-bottom-3 duration-300">
        <div className="w-full max-w-[300px] h-16 flex items-center justify-between px-2 rounded-full bg-background/90 dark:bg-card/90 backdrop-blur-2xl border border-border/80 shadow-[0_12px_36px_rgba(0,0,0,0.18)] pointer-events-auto shrink-0 gap-1.5">
          
          {/* UBER RIDE BUTTON */}
          <button
            onClick={() => triggerRideHail("uber")}
            className="flex-1 h-12 rounded-full bg-foreground text-background font-extrabold text-xs flex items-center justify-center shadow-xs hover:opacity-90 transition-opacity px-3"
            title="Book Uber to ER"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-auto fill-current shrink-0" viewBox="0 0 926.905 321.777">
              <path d="M53.328 229.809q5.875 15.593 16.27 26.664q10.395 11.073 24.63 16.948q14.236 5.875 30.958 5.875q16.27 0 30.506-6.102c14.236-6.102 17.776-9.792 24.856-17.173q10.62-11.072 16.496-26.438c5.876-15.366 5.875-21.692 5.875-34.347V0h47.453v316.354h-47.001v-29.376q-15.818 16.72-37.285 25.761q-21.467 9.038-46.323 9.038q-25.309 0-47.228-8.813q-21.919-8.812-37.962-25.082c-16.043-16.27-19.132-23.876-25.308-39.092Q0 225.968 0 197.947V0h47.453v195.236q0 18.982 5.875 34.573M332.168 0v115.243q15.818-15.817 36.607-25.082c20.789-9.265 28.924-9.265 45.193-9.265q25.308 0 47.453 9.49q22.144 9.49 38.414 25.761c16.27 16.271 19.434 23.651 25.761 38.414q9.49 22.146 9.49 47.002q0 24.855-9.49 46.774q-9.49 21.92-25.761 38.188q-16.27 16.27-38.414 25.761q-22.146 9.49-47.453 9.49q-24.404 0-45.419-9.265q-21.015-9.264-36.833-25.082v28.924h-45.193V0zm5.197 232.746q6.101 14.463 16.948 25.309c10.847 10.846 15.667 12.956 25.308 17.174q14.462 6.327 31.184 6.327q16.27 0 30.731-6.327c14.461-6.327 18.001-9.942 25.083-17.174q10.62-10.846 16.947-25.309q6.327-14.461 6.327-31.183c0-16.722-2.109-21.618-6.327-31.41s-9.867-18.303-16.947-25.534q-10.62-10.846-25.083-16.947c-14.463-6.101-19.885-6.102-30.731-6.102s-21.09 2.034-30.731 6.102s-18.077 9.717-25.309 16.947q-10.846 10.846-17.173 25.534c-6.327 14.688-6.327 20.262-6.327 31.41q-.001 16.722 6.1 31.183m223.477-77.732q9.039-21.693 24.856-38.188c15.817-16.495 23.049-19.659 37.511-25.986s30.129-9.49 47.001-9.49q24.856 0 46.098 9.038q21.24 9.039 36.606 25.083t23.952 37.962q8.587 21.92 8.587 47.68v14.914H597.901q2.26 14.01 9.039 25.985q6.78 11.976 16.947 20.789q10.168 8.814 23.049 13.784t27.342 4.972q41.127 0 66.435-33.896l32.991 24.404q-17.173 23.05-42.481 36.155q-25.31 13.106-56.944 13.106q-25.76 0-48.131-9.039c-22.371-9.039-27.869-14.462-38.866-25.309s-19.659-23.576-25.986-38.188s-9.491-30.506-9.491-47.679q-.002-24.404 9.037-46.097m63.497-17.852q-19.207 16.044-25.534 42.708h140.552q-5.875-26.664-25.083-42.708t-44.967-16.043q-25.76 0-44.968 16.043m246.527 5.197q-14.462 15.817-14.462 42.934v131.062h-45.646V85.868h45.193v28.472q8.588-14.01 22.371-22.145t32.766-8.136h15.817v42.482h-18.981q-22.596.001-37.058 15.818" />
            </svg>
          </button>

          {/* OLA RIDE BUTTON */}
          <button
            onClick={() => triggerRideHail("ola")}
            className="flex-1 h-12 rounded-full bg-muted hover:bg-muted/80 text-foreground font-extrabold text-xs flex items-center justify-center transition-colors px-3"
            title="Book Ola to ER"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-auto fill-current shrink-0" viewBox="-0.578 -0.578 51.974 20.409">
              <path d="M9.588 0a9.53 9.53 0 0 0-5.322 1.615A9.6 9.6 0 0 0 .733 5.934a9.67 9.67 0 0 0-.55 5.562a9.65 9.65 0 0 0 2.616 4.934a9.53 9.53 0 0 0 10.438 2.092a9.6 9.6 0 0 0 4.299-3.545A9.664 9.664 0 0 0 16.35 2.824A9.55 9.55 0 0 0 9.588 0m11.764.64V18.6h8.076l2.24-4.2H25.53L25.542.64zm19.893.028L31.669 18.6h4.748l4.828-9.053L46.07 18.6h4.748zM9.319 4.448a5.14 5.14 0 0 1 4.545 2.296c.567.853.871 1.857.871 2.883a5.2 5.2 0 0 1-1.52 3.668a5.16 5.16 0 0 1-3.636 1.52a5.14 5.14 0 0 1-2.86-.87a5.2 5.2 0 0 1-1.906-2.324a5.21 5.21 0 0 1 1.11-5.656a5.15 5.15 0 0 1 3.396-1.518" />
            </svg>
          </button>

          {/* CURRENT LOCATION BUTTON: re-reads GPS and re-runs the ER ladder.
              Icon combines the rotate arrows with the pin, so it reads as
              "refresh my location" at a glance. */}
          <button
            onClick={handleRefreshLocation}
            disabled={isRefreshingLocation}
            className="h-12 w-12 rounded-full bg-primary/10 text-primary border border-primary/20 font-extrabold flex items-center justify-center shrink-0 hover:bg-primary/20 transition-colors disabled:opacity-60"
            title="Refresh my location"
            aria-label="Refresh my location"
          >
            <RefreshLocationIcon
              className="h-6 w-6"
              spin={isRefreshingLocation}
            />
          </button>

        </div>
      </div>

      <MobileNav onOpenMedicalId={() => setIsMedicalIdOpen(true)} />
      <QuickMedicalIdModal isOpen={isMedicalIdOpen} onClose={() => setIsMedicalIdOpen(false)} />

      {/* Driver Card Flashcard Modal */}
      <Dialog open={isDriverCardOpen} onOpenChange={setIsDriverCardOpen}>
        <DialogContent className="sm:max-w-md rounded-3xl p-6 bg-card border border-border">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg font-bold">
              <FaCar className="h-5 w-5 text-primary" />
              Emergency Driver Card
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 pt-2">
            <div className="rounded-2xl bg-amber-500/10 border border-amber-500/30 p-4 space-y-2">
              <p className="text-xs font-bold text-amber-700 dark:text-amber-300 uppercase tracking-wide">
                Show this to your Taxi / Auto Driver:
              </p>
              <div className="space-y-2 text-foreground">
                <div>
                  <p className="text-xs text-muted-foreground font-semibold">Hindi:</p>
                  <p className="text-base font-extrabold">कृपया मुझे निकटतम आपातकालीन अस्पताल ले चलें। यह एक मेडिकल इमरजेंसी है।</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-semibold">Marathi:</p>
                  <p className="text-base font-extrabold">कृपया मला जवळच्या आपत्कालीन रुग्णालयात घेऊन चला. ही वैद्यकीय आणीबाणी आहे.</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-semibold">English:</p>
                  <p className="text-sm font-medium">Please take me to the nearest emergency hospital immediately. This is a medical emergency.</p>
                </div>
              </div>
            </div>

            {nearestHospital && (
              <div className="rounded-2xl bg-muted/60 border border-border p-3.5 space-y-1.5">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-muted-foreground">Target Hospital:</p>
                  {nearestHospital.isGeneralOrMultispeciality && (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                      General / Multi-Speciality
                    </span>
                  )}
                </div>
                <p className="text-sm font-bold text-foreground">{nearestHospital.name}</p>
                <p className="text-xs text-muted-foreground">{nearestHospital.address}</p>
              </div>
            )}

            <Button
              onClick={() => setIsDriverCardOpen(false)}
              className="w-full rounded-2xl h-11 font-bold"
            >
              Done
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ─── BridgeStem ───────────────────────────────────────────────────────────────
// Renders a small convex capsule that protrudes from the shelf bottom toward the
// water-drop circle. It creates the visual "connection" between shelf and pill.
// shelfWidth            – rendered width of the shelf (px)
// tabOffsetFromShelfLeft – horizontal center of the active tab relative to shelf (px)
// circleR               – radius of the water-drop circle (px)
function BridgeStem({
  shelfWidth,
  tabOffsetFromShelfLeft,
  circleR,
}: {
  shelfWidth: number;
  tabOffsetFromShelfLeft: number;
  circleR: number;
}) {
  const cx = tabOffsetFromShelfLeft;
  const r = circleR;        // 26
  const stemW = r * 1.6;   // 41.6 — visible width of the downward capsule
  const stemH = 14;         // height of the stem (matches SVG height)

  // Draw a rounded rectangle (capsule bottom) that bridges downward
  const left = cx - stemW / 2;
  const right = cx + stemW / 2;
  const capR = stemW / 2;  // fully rounded sides

  const path = [
    `M ${left} 0`,
    `L ${right} 0`,
    `L ${right} ${stemH - capR}`,
    `A ${capR} ${capR} 0 0 1 ${left} ${stemH - capR}`,
    `Z`,
  ].join(' ');

  return (
    <path
      d={path}
      className="fill-background/90 dark:fill-card/90"
    />
  );
}
