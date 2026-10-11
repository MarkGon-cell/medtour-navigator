import { useState } from "react";
import { MapPin, Navigation, Phone, BedDouble, Siren, Sparkles } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

import { HospitalAiDialog } from "@/components/dashboard/HospitalAiDialog";

type Hospital = {
  id: number;
  name: string;
  city: string | null;
  state: string;
  district: string | null;
  address: string | null;
  pincode: string | null;
  latitude: number;
  longitude: number;
  specialties: string | null;
  facilities: string | null;
  emergency_available: boolean;
  emergency_services: string | null;
  ambulance_phone: string | null;
  phone: string | null;
  website: string | null;
  total_beds: number | null;
  tariff_range: string | null;
  distance_km?: number;
  ai_match_score?: number;
  ai_match_reason?: string;
};

interface HospitalCardProps {
  hospital: any;
}

export function HospitalCard({ hospital }: HospitalCardProps) {
  const navigate = useNavigate();

  // Clicking anywhere on the card asks Google AI for more on this hospital.
  const [showAi, setShowAi] = useState(false);

  // Google Maps turn-by-turn navigation to the facility coordinates.
  const handleNavigate = () => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}`;
    window.open(url, "_blank");
  };

  // The national directory carries a phone number for only a fraction of
  // facilities (see docs/architecture.md), so "Call" looks the hospital up
  // on Google instead of dialling a number that may not exist.
  const handleCall = () => {
    const query = [hospital.name, hospital.city, hospital.state]
      .filter(Boolean)
      .join(" ");
    const url = `https://www.google.com/search?q=${encodeURIComponent(query)}`;
    window.open(url, "_blank");
  };

  const handleDetails = () => {
    navigate({
      to: `/hospital-details/${hospital.id}`,
    });
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Google AI overview for ${hospital.name}`}
      onClick={() => setShowAi(true)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setShowAi(true);
        }
      }}
      className="group cursor-pointer rounded-2xl border border-border bg-card p-5 shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-2 focus-visible:outline-primary"
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-base font-semibold leading-tight text-foreground">
              {hospital.name}
            </h3>
            {hospital.ai_match_score !== undefined && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 dark:border-emerald-700/60 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-300">
                <Sparkles className="h-3 w-3" />
                {hospital.ai_match_score}% AI Match
              </span>
            )}
          </div>

          <div className="mt-2 flex items-center gap-1.5 text-sm text-muted-foreground">
            <MapPin className="h-4 w-4 shrink-0" />
            <span>
              {hospital.city || hospital.district || "Location unavailable"}
              {hospital.state ? `, ${hospital.state}` : ""}
            </span>
          </div>
        </div>

        {/* Emergency Badge */}
        {hospital.emergency_available && (
          <span className="flex shrink-0 items-center gap-1 rounded-full bg-destructive/10 px-2.5 py-1 text-xs font-medium text-destructive">
            <Siren className="h-3.5 w-3.5" />
            Emergency
          </span>
        )}
      </div>

      {/* AI Match Reason Banner */}
      {hospital.ai_match_reason && (
        <div className="mt-3 rounded-xl bg-muted/60 border border-border/80 px-3 py-2 text-xs font-medium text-foreground/90">
          <span className="text-primary font-bold mr-1">Why it's best and recommended:</span>
          {hospital.ai_match_reason}
        </div>
      )}

      {/* Distance */}
      {hospital.distance_km !== undefined && (
        <div className="mt-3 text-sm font-medium text-foreground">
          {hospital.distance_km.toFixed(2)} km away
        </div>
      )}

      {/* Specialties */}
      {hospital.specialties && (
        <div className="mt-3">
          <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
            Specialties
          </p>
          <div className="flex flex-wrap gap-1.5 max-h-24 overflow-hidden">
            {Array.from(
              new Set<string>(
                String(hospital.specialties)
                  .split(/\\n|\n|,|;/)
                  .map((s) => s.trim())
                  .filter((s) => s.length > 0)
              )
            )
              .slice(0, 8)
              .map((spec, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center rounded-lg bg-muted px-2.5 py-1 text-xs font-medium text-foreground"
                >
                  {spec}
                </span>
              ))}
          </div>
        </div>
      )}

      {/* Information */}
      <div className="mt-4 grid grid-cols-2 gap-3">
        {hospital.total_beds !== null && hospital.total_beds !== undefined && (
          <div className="rounded-xl bg-muted/50 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <BedDouble className="h-4 w-4" />
              <span className="text-xs">Beds</span>
            </div>
            <p className="mt-1 text-sm font-semibold text-foreground">
              {hospital.total_beds && hospital.total_beds > 0
                ? hospital.total_beds
                : "Not available"}
            </p>
          </div>
        )}

        {hospital.phone && (
          <div className="rounded-xl bg-muted/50 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="h-4 w-4" />
              <span className="text-xs">Contact</span>
            </div>
            <p className="mt-1 truncate text-sm font-semibold text-foreground">
              {hospital.phone}
            </p>
          </div>
        )}
      </div>

      {/* Address */}
      {hospital.address && (
        <p className="mt-4 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
          {hospital.address}
        </p>
      )}

      {/* Hint that the whole card is clickable */}
      <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Sparkles className="h-3 w-3 shrink-0 text-primary" />
        Tap the card for a Google AI overview of this hospital
      </p>

      {/* Actions */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            handleCall();
          }}
          title="Google this hospital to reach it"
          className="flex items-center justify-center gap-1.5 rounded-xl border border-border px-2 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          <Phone className="h-4 w-4 shrink-0" />
          Call
        </button>

        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            handleDetails();
          }}
          className="rounded-xl border border-border px-2 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          Details
        </button>

        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            handleNavigate();
          }}
          title="Directions in Google Maps"
          className="flex items-center justify-center gap-1.5 rounded-xl bg-primary px-2 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Navigation className="h-4 w-4 shrink-0" />
          Directions
        </button>
      </div>

      {/* Google AI overview, opened by clicking the card */}
      <HospitalAiDialog
        hospital={
          showAi
            ? {
                name: hospital.name,
                city: hospital.city,
                state: hospital.state,
              }
            : null
        }
        onClose={() => setShowAi(false)}
      />
    </div>
  );
}
