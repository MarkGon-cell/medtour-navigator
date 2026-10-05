import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import api from "@/lib/api";

import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { HospitalLocationMap } from "@/components/dashboard/HospitalLocationMap";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import {
  ArrowLeft,
  MapPin,
  Phone,
  Stethoscope,
  Ambulance,
  Bed,
  Navigation,
  Globe,
  Mail,
  UserRound,
  Building2,
  ShieldCheck,
  Clock,
} from "lucide-react";

// ---------------------------------------------------------
// Hospital type returned by FastAPI
// ---------------------------------------------------------

type Hospital = {
  id: number;
  name: string;

  category: string | null;
  care_type: string | null;
  discipline: string | null;

  city: string | null;
  state: string;
  district: string | null;
  subdistrict: string | null;
  address: string | null;
  pincode: string | null;

  latitude: number;
  longitude: number;

  specialties: string | null;
  facilities: string | null;
  miscellaneous_facilities: string | null;

  emergency_available: boolean;
  emergency_services: string | null;
  emergency_phone: string | null;
  ambulance_phone: string | null;
  bloodbank_phone: string | null;

  phone: string | null;
  mobile: string | null;
  tollfree: string | null;
  helpline: string | null;
  website: string | null;
  email: string | null;

  total_beds: number | null;
  private_wards: number | null;
  economically_weaker_beds: number | null;

  doctors: number | null;
  medical_consultants: number | null;

  established_year: number | null;
  accreditation: string | null;
  registration_number: string | null;
  empanelment: string | null;

  tariff_range: string | null;
};

type HospitalAvailability = {
  hospital_id: number;
  availability_available: boolean;
  available_general_beds?: number | null;
  available_icu_beds?: number | null;
  available_emergency_beds?: number | null;
  emergency_status?: string | null;
  source_type?: string | null;
  source_url?: string | null;
  observed_at?: string | null;
  expires_at?: string | null;
  confidence?: number | null;
  message?: string;
};

interface WaitingTimePrediction {
  prediction_available: boolean;
  predicted_waiting_minutes?: number;
  model_version?: string;
  message?: string;
}
// ---------------------------------------------------------
// Display helpers
// ---------------------------------------------------------

const displayValue = (
  value: string | number | null | undefined
) => {
  if (
    value === null ||
    value === undefined ||
    value === "" ||
    value === "0" ||
    value === "0.0"
  ) {
    return "Not available in directory";
  }

  return String(value);
};

const displayNumber = (
  value: number | null | undefined
) => {
  if (
    value === null ||
    value === undefined ||
    value <= 0
  ) {
    return "Not available in directory";
  }

  return value.toString();
};

/*
 * Presence check used to hide fields the hospital
 * has not provided, instead of printing
 * "Not available in directory" everywhere.
 */
function has<T>(
  value: T
): value is Exclude<T, null | undefined | "" | "0" | "0.0"> {
  if (value === null || value === undefined) return false;

  if (typeof value === "boolean") return value;

  if (typeof value === "number") return Number.isFinite(value);

  const trimmed = String(value).trim();

  return (
    trimmed.length > 0 &&
    trimmed !== "0" &&
    trimmed !== "0.0" &&
    trimmed.toLowerCase() !== "null" &&
    trimmed.toLowerCase() !== "none" &&
    trimmed.toLowerCase() !== "n/a" &&
    trimmed.toLowerCase() !== "na"
  );
}

/*
 * Splits raw directory strings (specialties,
 * facilities, ...) into a clean de-duplicated list.
 */
const splitList = (
  value: string | null | undefined
): string[] => {
  if (!has(value)) return [];

  return Array.from(
    new Set(
      String(value)
        .split(/\\n|\n|,|;|\||\u2022/)
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0)
    )
  );
};

// ---------------------------------------------------------
// Small label/value row used inside dense panels
// ---------------------------------------------------------

function Detail({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="text-xs font-medium">{value}</p>
    </div>
  );
}

// ---------------------------------------------------------
// Route
// ---------------------------------------------------------

export const Route = createFileRoute("/hospital-details/$hospitalId")({
  component: HospitalDetails,
});

// ---------------------------------------------------------
// Hospital Details Page
// ---------------------------------------------------------

function HospitalDetails() {
  const { hospitalId } = Route.useParams();

  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [availability, setAvailability] = useState<HospitalAvailability | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [waitingPrediction, setWaitingPrediction] =
  useState<WaitingTimePrediction | null>(null);
  const [waitingLoading, setWaitingLoading] =
  useState(false);

  // -------------------------------------------------------
  // Fetch hospital from FastAPI
  // -------------------------------------------------------

  useEffect(() => {
  const loadHospital = async () => {
    try {
      setLoading(true);

      const response = await api.get(
        `/hospitals/${hospitalId}`
      );

      setHospital(response.data);

      // Load availability
      try {
        const availabilityResponse =
          await api.get(
            `/hospitals/${hospitalId}/availability`
          );

        if (
          availabilityResponse.data
            .availability_available
        ) {
          setAvailability(
            availabilityResponse.data
          );
        }
      } catch (error) {
        console.error(
          "Failed to load availability:",
          error
        );
      }

    } catch (error) {
      console.error(
        "Failed to load hospital:",
        error
      );
    } finally {
      setLoading(false);
    }
  };

  if (hospitalId) {
    loadHospital();
  }
}, [hospitalId]);

useEffect(() => {
  const loadWaitingPrediction = async () => {
    try {
      setWaitingLoading(true);

      const now = new Date();

      const month = now.getMonth() + 1;

      // JavaScript:
      // Sunday = 0
      // NHAMCS:
      // Sunday = 1
      const dayOfWeek = now.getDay();

      const vdayr =
        dayOfWeek === 0
          ? 1
          : dayOfWeek + 1;

      const hours = now.getHours();
      const minutes = now.getMinutes();

      const arrtime =
        hours * 100 + minutes;

      const response = await api.post(
        "/waiting-time/predict",
        {
          vmonth: month,
          vdayr,
          arrtime,
          age: 30,
          immedr: 3,
          painscale: 0,
          lov: 1,
          admithos: 0,
          board: 0,
        }
      );

      setWaitingPrediction(
        response.data
      );

    } catch (error) {
      console.error(
        "Failed to load waiting-time prediction:",
        error
      );

      setWaitingPrediction(null);

    } finally {
      setWaitingLoading(false);
    }
  };

  loadWaitingPrediction();
}, []);

  // -------------------------------------------------------
  // Navigate to Google Maps
  // -------------------------------------------------------

  const handleNavigate = () => {
    if (!hospital) return;

    window.open(
      `https://www.openstreetmap.org/?mlat=${hospital.latitude}&mlon=${hospital.longitude}#map=16/${hospital.latitude}/${hospital.longitude}`,
      "_blank"
    );
  };

  // -------------------------------------------------------
  // Back button
  // -------------------------------------------------------

  const handleBack = () => {
    window.history.back();
  };

  // -------------------------------------------------------
  // Parallax: map layer sits fixed behind the scroll layer.
  // As the details sheet scrolls up it covers the map, and
  // the map drifts upward slightly slower (parallax feel).
  // -------------------------------------------------------

  const scrollRef = useRef<HTMLDivElement>(null);
  const mapLayerRef = useRef<HTMLDivElement>(null);

  const handleSheetScroll = () => {
    const scroller = scrollRef.current;
    const mapLayer = mapLayerRef.current;

    if (!scroller || !mapLayer) return;

    const y = scroller.scrollTop;

    // Map drifts upward at ~30% of the sheet's speed (pure
    // translate — never scale, so the map always covers the
    // viewport and the exposed bottom gap stays under the sheet).
    mapLayer.style.transform = `translate3d(0, ${-y * 0.3}px, 0)`;
  };

  // -------------------------------------------------------
  // Loading state
  // -------------------------------------------------------

  return (
    <div className="flex h-[100dvh] w-full overflow-hidden bg-background">
      {/* Desktop Sidebar (hidden on small screens) */}
      <DashboardSidebar className="hidden md:block" />

      <main className="relative flex-1 overflow-hidden">
        {/* ============================================ */}
        {/* MAP LAYER — fixed behind, fills the screen  */}
        {/* ============================================ */}
        <div
          ref={mapLayerRef}
          className="absolute inset-0 z-0 will-change-transform"
        >
          {loading && (
            <div className="h-full w-full animate-pulse bg-muted/60" />
          )}

          {!loading && !error && hospital && (
            <HospitalLocationMap
              latitude={hospital.latitude}
              longitude={hospital.longitude}
              hospitalName={hospital.name}
              city={hospital.city}
              state={hospital.state}
            />
          )}
        </div>

        {/* Floating back button over the map */}
        <button
          type="button"
          onClick={handleBack}
          aria-label="Go back"
          className="absolute left-3 top-3 z-30 flex h-10 w-10 items-center justify-center rounded-full bg-background/85 text-foreground shadow-md backdrop-blur transition hover:bg-background sm:left-4 sm:top-4"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>

        {/* ============================================ */}
        {/* SCROLL LAYER — spacer reveals the map, then  */}
        {/* the details sheet slides up and covers it     */}
        {/* ============================================ */}
        <div
          ref={scrollRef}
          onScroll={handleSheetScroll}
          className="absolute inset-0 z-10 overflow-y-auto overscroll-contain"
        >
          {/* Transparent spacer — map shows through here */}
          <div className="h-[74%]" />

          {/* Details sheet — rounded top, slides over map */}
          <section className="relative rounded-t-3xl border-t border-border/60 bg-background shadow-[0_-10px_40px_rgba(0,0,0,0.18)]">
            {/* Drag grabber */}
            <div className="sticky top-0 z-20 flex justify-center rounded-t-3xl bg-background pb-1 pt-2.5">
              <span className="h-1 w-10 rounded-full bg-muted-foreground/30" />
            </div>

            <div className="mx-auto max-w-5xl px-3 pb-8 sm:px-4">

          {loading && (
            <Card className="rounded-2xl">
              <CardContent className="p-4 sm:p-6">
                <div className="animate-pulse space-y-4">

                  <div className="h-6 w-2/3 rounded bg-muted sm:h-8" />

                  <div className="h-4 w-1/3 rounded bg-muted" />

                  <div className="h-20 rounded bg-muted" />

                  <div className="grid grid-cols-2 gap-4">
                    <div className="h-24 rounded bg-muted" />
                    <div className="h-24 rounded bg-muted" />
                  </div>

                </div>
              </CardContent>
            </Card>
          )}

          {/* ------------------------------------------------ */}
          {/* Error */}
          {/* ------------------------------------------------ */}

          {!loading && error && (
            <Card className="rounded-2xl">
              <CardContent className="p-4 sm:p-6 text-center">
                <p className="text-sm text-destructive">
                  {error}
                </p>
              </CardContent>
            </Card>
          )}

          {/* ------------------------------------------------ */}
          {/* Hospital Details */}
          {/* ------------------------------------------------ */}

          {!loading && hospital && (
            <>
{/* Compact header strip */}
              <div className="-mx-3 -mt-1 bg-primary px-3 py-3 text-white sm:-mx-4 sm:px-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <h1 className="text-base font-bold leading-tight sm:text-lg">
                      {hospital.name}
                    </h1>

                    {(has(hospital.city) || has(hospital.district)) && (
                      <p className="mt-1 flex items-start gap-1 text-[11px] text-white/80 sm:text-xs">
                        <MapPin className="mt-0.5 h-3 w-3 shrink-0" />
                        <span>
                          {Array.from(
                            new Set(
                              [hospital.city, hospital.district, hospital.state].filter(
                                (part): part is string => has(part)
                              )
                            )
                          ).join(", ")}
                        </span>
                      </p>
                    )}
                  </div>

                  {hospital.emergency_available && (
                    <Badge className="shrink-0 bg-emergency text-[10px] text-emergency-foreground">
                      24/7 Emergency
                    </Badge>
                  )}
                </div>
              </div>

              {/* Quick actions — only what the hospital provides */}
              {(has(hospital.emergency_phone) ||
                has(hospital.ambulance_phone) ||
                has(hospital.bloodbank_phone) ||
                has(hospital.phone) ||
                has(hospital.mobile)) && (
                <div className="-mx-3 mt-3 flex gap-2 overflow-x-auto px-3 pb-1 sm:-mx-4 sm:px-4">
                  {has(hospital.emergency_phone) && (
                    <a
                      href={`tel:${hospital.emergency_phone}`}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl bg-destructive px-3 py-2 text-xs font-semibold text-white"
                    >
                      <Ambulance className="h-4 w-4" />
                      Emergency
                    </a>
                  )}

                  {has(hospital.ambulance_phone) && (
                    <a
                      href={`tel:${hospital.ambulance_phone}`}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-semibold"
                    >
                      <Ambulance className="h-4 w-4" />
                      Ambulance
                    </a>
                  )}

                  {has(hospital.bloodbank_phone) && (
                    <a
                      href={`tel:${hospital.bloodbank_phone}`}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-semibold"
                    >
                      <Phone className="h-4 w-4" />
                      Blood Bank
                    </a>
                  )}

                  {has(hospital.phone) && (
                    <a
                      href={`tel:${hospital.phone}`}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-semibold"
                    >
                      <Phone className="h-4 w-4" />
                      {hospital.phone}
                    </a>
                  )}

                  {has(hospital.mobile) && (
                    <a
                      href={`tel:${hospital.mobile}`}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-xs font-semibold"
                    >
                      <Phone className="h-4 w-4" />
                      {hospital.mobile}
                    </a>
                  )}
                </div>
              )}

              {/* Key numbers — only available ones */}
              {(has(hospital.total_beds) ||
                hospital.emergency_available ||
                has(hospital.specialties) ||
                (waitingPrediction?.prediction_available &&
                  has(waitingPrediction.predicted_waiting_minutes))) && (
                <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {has(hospital.total_beds) && (
                    <div className="rounded-xl bg-card p-2.5 ring-1 ring-border">
                      <Bed className="h-4 w-4 text-primary" />
                      <p className="mt-1 text-base font-bold">
                        {hospital.total_beds}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        Total Beds
                      </p>
                    </div>
                  )}

                  {has(hospital.doctors) && (
                    <div className="rounded-xl bg-card p-2.5 ring-1 ring-border">
                      <Stethoscope className="h-4 w-4 text-primary" />
                      <p className="mt-1 text-base font-bold">
                        {hospital.doctors}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        Doctors
                      </p>
                    </div>
                  )}

                  {hospital.emergency_available && (
                    <div className="rounded-xl bg-card p-2.5 ring-1 ring-border">
                      <Ambulance className="h-4 w-4 text-destructive" />
                      <p className="mt-1 text-sm font-bold text-destructive">
                        24/7
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        Emergency
                      </p>
                    </div>
                  )}

                  {waitingPrediction?.prediction_available &&
                    has(waitingPrediction.predicted_waiting_minutes) && (
                      <div className="rounded-xl bg-card p-2.5 ring-1 ring-border">
                        <Clock className="h-4 w-4 text-primary" />
                        <p className="mt-1 text-base font-bold">
                          ~{waitingPrediction.predicted_waiting_minutes}m
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          Est. Wait
                        </p>
                      </div>
                    )}
                </div>
              )}

              {/* Specialties — chips, only when present */}
              {splitList(hospital.specialties).length > 0 && (
                <section className="mt-3 rounded-xl bg-card p-3 ring-1 ring-border">
                  <h2 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                    <Stethoscope className="h-3.5 w-3.5 text-primary" />
                    Specialties
                  </h2>

                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {splitList(hospital.specialties).map((spec) => (
                      <span
                        key={spec}
                        className="rounded-lg bg-muted px-2 py-1 text-[11px] font-medium"
                      >
                        {spec}
                      </span>
                    ))}
                  </div>
                </section>
              )}

              {/* Live bed availability — only when backend provides it */}
              {availability?.availability_available && (
                <section className="mt-3 rounded-xl bg-card p-3 ring-1 ring-border">
                  <h2 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                    <Bed className="h-3.5 w-3.5 text-primary" />
                    Beds Available Now
                  </h2>

                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {has(availability.available_general_beds) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-lg font-bold">
                          {availability.available_general_beds}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          General
                        </p>
                      </div>
                    )}

                    {has(availability.available_icu_beds) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-lg font-bold">
                          {availability.available_icu_beds}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          ICU
                        </p>
                      </div>
                    )}

                    {has(availability.available_emergency_beds) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-lg font-bold text-destructive">
                          {availability.available_emergency_beds}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          Emergency
                        </p>
                      </div>
                    )}
                  </div>

                  {(has(availability.emergency_status) ||
                    has(availability.source_type) ||
                    has(availability.observed_at)) && (
                    <div className="mt-2 space-y-0.5 text-[11px] text-muted-foreground">
                      {has(availability.emergency_status) && (
                        <p>
                          Status:{" "}
                          <span className="font-medium text-foreground">
                            {availability.emergency_status}
                          </span>
                        </p>
                      )}

                      {has(availability.observed_at) && (
                        <p>
                          Updated{" "}
                          {new Date(
                            availability.observed_at
                          ).toLocaleString()}
                        </p>
                      )}
                    </div>
                  )}
                </section>
              )}

              {/* Everything else that the hospital actually has */}
              {(has(hospital.category) ||
                has(hospital.care_type) ||
                has(hospital.discipline) ||
                has(hospital.established_year) ||
                has(hospital.accreditation) ||
                has(hospital.registration_number) ||
                has(hospital.empanelment) ||
                has(hospital.tariff_range) ||
                has(hospital.subdistrict) ||
                has(hospital.pincode) ||
                has(hospital.facilities) ||
                has(hospital.miscellaneous_facilities) ||
                has(hospital.emergency_services) ||
                has(hospital.tollfree) ||
                has(hospital.helpline) ||
                has(hospital.email) ||
                has(hospital.website)) && (
                <section className="mt-3 overflow-hidden rounded-xl bg-card ring-1 ring-border">
                  {/* Address */}
                  {(has(hospital.address) ||
                    has(hospital.subdistrict) ||
                    has(hospital.pincode)) && (
                    <div className="flex gap-2 border-b border-border/60 p-3">
                      <MapPin className="h-4 w-4 shrink-0 text-primary" />
                      <p className="text-xs leading-relaxed">
                        {has(hospital.address) && (
                          <span className="block">
                            {hospital.address}
                          </span>
                        )}

                        {has(hospital.subdistrict) && (
                          <span className="block text-muted-foreground">
                            {hospital.subdistrict}
                          </span>
                        )}

                        {has(hospital.pincode) && (
                          <span className="block text-muted-foreground">
                            PIN {hospital.pincode}
                          </span>
                        )}
                      </p>
                    </div>
                  )}

                  {/* Facilities */}
                  {splitList(hospital.facilities).length > 0 && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        Facilities
                      </h3>

                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {splitList(hospital.facilities).map((item) => (
                          <span
                            key={item}
                            className="rounded-lg bg-muted px-2 py-0.5 text-[11px]"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {splitList(hospital.miscellaneous_facilities).length > 0 && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        Additional Facilities
                      </h3>

                      <div className="mt-1.5 flex flex-wrap gap-1.5">
                        {splitList(
                          hospital.miscellaneous_facilities
                        ).map((item) => (
                          <span
                            key={item}
                            className="rounded-lg bg-muted px-2 py-0.5 text-[11px]"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Classification */}
                  {(has(hospital.category) ||
                    has(hospital.care_type) ||
                    has(hospital.discipline) ||
                    has(hospital.established_year)) && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        <Building2 className="h-3.5 w-3.5 text-primary" />
                        Classification
                      </h3>

                      <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1.5">
                        {has(hospital.category) && (
                          <Detail label="Category" value={hospital.category} />
                        )}

                        {has(hospital.care_type) && (
                          <Detail label="Care Type" value={hospital.care_type} />
                        )}

                        {has(hospital.discipline) && (
                          <Detail
                            label="Discipline"
                            value={hospital.discipline}
                          />
                        )}

                        {has(hospital.established_year) && (
                          <Detail
                            label="Established"
                            value={hospital.established_year}
                          />
                        )}
                      </div>
                    </div>
                  )}

                  {/* Emergency services detail */}
                  {has(hospital.emergency_services) && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        <Ambulance className="h-3.5 w-3.5 text-destructive" />
                        Emergency Services
                      </h3>

                      <p className="mt-1.5 text-xs">
                        {hospital.emergency_services}
                      </p>
                    </div>
                  )}

                  {/* Accreditation */}
                  {(has(hospital.accreditation) ||
                    has(hospital.registration_number) ||
                    has(hospital.empanelment)) && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                        Accreditation
                      </h3>

                      <div className="mt-1.5 space-y-1">
                        {has(hospital.accreditation) && (
                          <p className="text-xs">
                            <span className="text-muted-foreground">
                              Accreditation:{" "}
                            </span>
                            {hospital.accreditation}
                          </p>
                        )}

                        {has(hospital.registration_number) && (
                          <p className="text-xs">
                            <span className="text-muted-foreground">
                              Registration:{" "}
                            </span>
                            {hospital.registration_number}
                          </p>
                        )}

                        {has(hospital.empanelment) && (
                          <p className="text-xs">
                            <span className="text-muted-foreground">
                              Empanelment:{" "}
                            </span>
                            {hospital.empanelment}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Remaining contact channels */}
                  {(has(hospital.tollfree) ||
                    has(hospital.helpline) ||
                    has(hospital.email) ||
                    has(hospital.website)) && (
                    <div className="border-b border-border/60 p-3">
                      <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        <Phone className="h-3.5 w-3.5 text-primary" />
                        Other Channels
                      </h3>

                      <div className="mt-1.5 space-y-1">
                        {has(hospital.tollfree) && (
                          <a
                            href={`tel:${hospital.tollfree}`}
                            className="block text-xs font-medium text-primary"
                          >
                            Toll-free: {hospital.tollfree}
                          </a>
                        )}

                        {has(hospital.helpline) && (
                          <a
                            href={`tel:${hospital.helpline}`}
                            className="block text-xs font-medium text-primary"
                          >
                            Helpline: {hospital.helpline}
                          </a>
                        )}

                        {has(hospital.email) && (
                          <a
                            href={`mailto:${hospital.email}`}
                            className="flex items-center gap-1.5 text-xs font-medium text-primary"
                          >
                            <Mail className="h-3.5 w-3.5 shrink-0" />
                            <span className="break-all">
                              {hospital.email}
                            </span>
                          </a>
                        )}

                        {has(hospital.website) && (
                          <a
                            href={
                              hospital.website.startsWith("http")
                                ? hospital.website
                                : `https://${hospital.website}`
                            }
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 text-xs font-medium text-primary"
                          >
                            <Globe className="h-3.5 w-3.5 shrink-0" />
                            Website
                          </a>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Tariff */}
                  {has(hospital.tariff_range) && (
                    <div className="p-3">
                      <h3 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                        Tariff Range
                      </h3>

                      <p className="mt-1 text-xs">
                        {hospital.tariff_range}
                      </p>
                    </div>
                  )}
                </section>
              )}

              {/* Capacity breakdown — only populated fields */}
              {(has(hospital.private_wards) ||
                has(hospital.economically_weaker_beds) ||
                has(hospital.medical_consultants)) && (
                <section className="mt-3 rounded-xl bg-card p-3 ring-1 ring-border">
                  <h2 className="text-xs font-bold uppercase tracking-wide text-muted-foreground">
                    Capacity Breakdown
                  </h2>

                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {has(hospital.private_wards) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-base font-bold">
                          {hospital.private_wards}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          Private
                        </p>
                      </div>
                    )}

                    {has(hospital.economically_weaker_beds) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-base font-bold">
                          {hospital.economically_weaker_beds}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          EWS
                        </p>
                      </div>
                    )}

                    {has(hospital.medical_consultants) && (
                      <div className="rounded-lg bg-muted/60 p-2 text-center">
                        <p className="text-base font-bold">
                          {hospital.medical_consultants}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          Consultants
                        </p>
                      </div>
                    )}
                  </div>
                </section>
              )}
              {/* ============================================ */}
              {/* Navigation */}
              {/* ============================================ */}

              <div className="sticky bottom-0 -mx-3 mt-4 border-t border-border/60 bg-background/95 px-3 py-3 backdrop-blur-sm sm:-mx-4 sm:px-4">
                <Button
                  size="lg"
                  className="w-full"
                  onClick={handleNavigate}
                >
                  <Navigation className="mr-2 h-4 w-4" />
                  Navigate via OpenStreetMap
                </Button>
              </div>

            </>
          )}

            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
