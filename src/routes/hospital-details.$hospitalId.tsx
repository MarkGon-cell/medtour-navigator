import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import api from "@/lib/api";

import { DashboardSidebar } from "@/components/dashboard/Sidebar";
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
      `https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}`,
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
  // Loading state
  // -------------------------------------------------------

  return (
    <div className="flex min-h-screen bg-muted/30">
      <DashboardSidebar />

      <main className="flex-1 p-4 sm:p-6">
        <div className="mx-auto max-w-5xl space-y-6">

          {/* Back Button */}
          <Button
            variant="ghost"
            onClick={handleBack}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>

          {/* ------------------------------------------------ */}
          {/* Loading */}
          {/* ------------------------------------------------ */}

          {loading && (
            <Card className="rounded-2xl">
              <CardContent className="p-8">
                <div className="animate-pulse space-y-4">

                  <div className="h-8 w-2/3 rounded bg-muted" />

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
              <CardContent className="p-8 text-center">
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
              {/* ============================================ */}
              {/* Hospital Header */}
              {/* ============================================ */}

              <Card className="overflow-hidden rounded-2xl">

                <div className="bg-gradient-hero p-6 text-white sm:p-8">

                  <div className="flex items-start justify-between gap-4">

                    <div className="min-w-0">

                      <p className="text-sm text-white/75">
                        Hospital
                      </p>

                      <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
                        {hospital.name}
                      </h1>

                      {/* Location */}
                      <div className="mt-3 flex items-start gap-2 text-sm">

                        <MapPin className="mt-0.5 h-4 w-4 shrink-0" />

                        <span>
                          {hospital.city
                            ? `${hospital.city}, `
                            : ""}
                          {hospital.state}
                        </span>

                      </div>

                      {/* District */}
                      {hospital.district && (
                        <p className="mt-1 pl-6 text-sm text-white/75">
                          {hospital.district}
                        </p>
                      )}

                    </div>

                    {/* Emergency Badge */}
                    {hospital.emergency_available && (
                      <Badge className="shrink-0 bg-emergency text-emergency-foreground">
                        24/7 Emergency
                      </Badge>
                    )}

                  </div>

                </div>

              </Card>

              {/* ============================================ */}
              {/* Hospital Summary Cards */}
              {/* ============================================ */}

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

                {/* Total Beds */}
                <Card className="rounded-2xl">

                  <CardContent className="p-5">

                    <Bed className="h-5 w-5 text-primary" />

                    <p className="mt-3 text-xl font-bold">
                      {displayNumber(hospital.total_beds)}
                    </p>

                    <p className="text-xs text-muted-foreground">
                      Total Beds
                    </p>

                  </CardContent>

                </Card>

                {/* Emergency */}
                <Card className="rounded-2xl">

                  <CardContent className="p-5">

                    <Ambulance className="h-5 w-5 text-primary" />

                    <p className="mt-3 text-xl font-bold">
                      {hospital.emergency_available
                        ? "Available"
                        : "Not Listed"}
                    </p>

                    <p className="text-xs text-muted-foreground">
                      Emergency Services
                    </p>

                  </CardContent>

                </Card>

                {/* Specialties */}
                <Card className="rounded-2xl">

                  <CardContent className="p-5">

                    <Stethoscope className="h-5 w-5 text-primary" />

                    <p className="mt-3 text-xl font-bold">
                      {hospital.specialties
                        ? "Available"
                        : "Not Listed"}
                    </p>

                    <p className="text-xs text-muted-foreground">
                      Specialties
                    </p>

                  </CardContent>

                </Card>

                {/* PIN Code */}
                <Card className="rounded-2xl">

                  <CardContent className="p-5">

                    <MapPin className="h-5 w-5 text-primary" />

                    <p className="mt-3 text-xl font-bold">
                      {displayValue(hospital.pincode)}
                    </p>

                    <p className="text-xs text-muted-foreground">
                      PIN Code
                    </p>

                  </CardContent>

                </Card>

              </div>

              {/* ============================================ */}
              {/* Basic Hospital Information */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="mb-5 flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Hospital Information
                    </h2>
                  </div>

                  <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Hospital Category
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.category)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Care Type
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.care_type)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Medical Discipline
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.discipline)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        City
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.city)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        District
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.district)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        PIN Code
                      </p>

                      <p className="mt-1 font-medium">
                        {displayValue(hospital.pincode)}
                      </p>
                    </div>

                  </div>

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Address */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <h2 className="font-semibold">
                    Address
                  </h2>

                  <p className="mt-2 flex gap-2 text-sm text-muted-foreground">

                    <MapPin className="h-4 w-4 shrink-0" />

                    <span>
                      {displayValue(hospital.address)}
                    </span>

                  </p>

                  {hospital.subdistrict && (
                    <p className="mt-2 text-sm text-muted-foreground">
                      Subdistrict: {hospital.subdistrict}
                    </p>
                  )}

                  {hospital.district && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {hospital.district}, {hospital.state}
                    </p>
                  )}

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Medical Information */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="flex items-center gap-2">
                    <Stethoscope className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Medical Information
                    </h2>
                  </div>

                  <div className="mt-6 space-y-6">

                    {/* Specialties */}
                    <div>
                      <p className="text-sm font-medium">
                        Specialties
                      </p>

                      <p className="mt-1 text-sm text-muted-foreground">
                        {displayValue(hospital.specialties)}
                      </p>
                    </div>

                    {/* Facilities */}
                    <div>
                      <p className="text-sm font-medium">
                        Facilities
                      </p>

                      <p className="mt-1 text-sm text-muted-foreground">
                        {displayValue(hospital.facilities)}
                      </p>
                    </div>

                    {/* Miscellaneous Facilities */}
                    <div>
                      <p className="text-sm font-medium">
                        Additional Facilities
                      </p>

                      <p className="mt-1 text-sm text-muted-foreground">
                        {displayValue(
                          hospital.miscellaneous_facilities
                        )}
                      </p>
                    </div>

                  </div>

                </CardContent>

              </Card>
                <Card>
  <CardContent className="p-6">
    <div className="flex items-center gap-3 mb-5">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
        <Bed className="h-5 w-5 text-primary" />
      </div>

      <div>
        <h2 className="text-lg font-semibold">
          Current Availability
        </h2>
        <p className="text-sm text-muted-foreground">
          Hospital availability information
        </p>
      </div>
    </div>

    {!availability?.availability_available ? (
      <div className="rounded-lg border border-dashed p-5">
        <p className="font-medium">
          Availability data not available
        </p>

        <p className="mt-1 text-sm text-muted-foreground">
          Current bed availability has not been provided by a
          verified source.
        </p>
      </div>
    ) : (
      <>
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border p-4">
            <p className="text-sm text-muted-foreground">
              General Beds
            </p>
            <p className="mt-1 text-2xl font-bold">
              {availability.available_general_beds ?? "—"}
            </p>
          </div>

          <div className="rounded-lg border p-4">
            <p className="text-sm text-muted-foreground">
              ICU Beds
            </p>
            <p className="mt-1 text-2xl font-bold">
              {availability.available_icu_beds ?? "—"}
            </p>
          </div>

          <div className="rounded-lg border p-4">
            <p className="text-sm text-muted-foreground">
              Emergency Beds
            </p>
            <p className="mt-1 text-2xl font-bold">
              {availability.available_emergency_beds ?? "—"}
            </p>
          </div>
        </div>

        {availability.emergency_status && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground">
              Emergency Status
            </p>

            <Badge className="mt-1">
              {availability.emergency_status}
            </Badge>
          </div>
        )}

        <div className="mt-5 rounded-lg bg-muted/50 p-4">
          <p className="text-sm">
            <span className="font-medium">Source:</span>{" "}
            {availability.source_type || "Not specified"}
          </p>

          {availability.observed_at && (
            <p className="mt-1 text-sm text-muted-foreground">
              Last updated:{" "}
              {new Date(
                availability.observed_at
              ).toLocaleString()}
            </p>
          )}
        </div>
      </>
    )}
  </CardContent>
</Card>
              {/* ============================================ */}
              {/* Hospital Capacity */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="flex items-center gap-2">
                    <Bed className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Hospital Capacity
                    </h2>
                  </div>

                  <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Total Beds
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(hospital.total_beds)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Private Wards
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(hospital.private_wards)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        EWS Beds
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(
                          hospital.economically_weaker_beds
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Doctors
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(hospital.doctors)}
                      </p>
                    </div>

                  </div>

                  <div className="mt-6 grid gap-6 sm:grid-cols-2">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Medical Consultants / Experts
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(
                          hospital.medical_consultants
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Established Year
                      </p>

                      <p className="mt-1 font-medium">
                        {displayNumber(
                          hospital.established_year
                        )}
                      </p>
                    </div>

                  </div>

                </CardContent>

              </Card>
              
              <Card>
  <CardContent className="p-6">
    <div className="flex items-start gap-4">
      <div className="rounded-lg bg-primary/10 p-3">
        <Clock className="h-6 w-6 text-primary" />
      </div>

      <div className="flex-1">
        <h3 className="font-semibold">
          AI Estimated Waiting Time
        </h3>

        {waitingLoading ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Calculating estimate...
          </p>
        ) : waitingPrediction?.prediction_available ? (
          <>
            <p className="mt-2 text-2xl font-bold">
              ~{waitingPrediction.predicted_waiting_minutes} minutes
            </p>

            <p className="mt-1 text-xs text-muted-foreground">
              AI-generated estimate
            </p>

            <p className="mt-2 text-xs text-muted-foreground">
              Model: Random Forest
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Waiting-time prediction is currently unavailable.
          </p>
        )}
      </div>
    </div>
  </CardContent>
</Card>

              {/* ============================================ */}
              {/* Emergency Services */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="flex items-center gap-2">
                    <Ambulance className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Emergency Services
                    </h2>
                  </div>

                  <div className="mt-6 grid gap-6 sm:grid-cols-2">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Emergency Availability
                      </p>

                      <div className="mt-2">
                        {hospital.emergency_available ? (
                          <Badge>
                            Emergency Available
                          </Badge>
                        ) : (
                          <Badge variant="outline">
                            Emergency Not Listed
                          </Badge>
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Emergency Services
                      </p>

                      <p className="mt-1">
                        {displayValue(
                          hospital.emergency_services
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Emergency Phone
                      </p>

                      {hospital.emergency_phone ? (
                        <a
                          href={`tel:${hospital.emergency_phone}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Phone className="h-4 w-4" />
                          {hospital.emergency_phone}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Ambulance
                      </p>

                      {hospital.ambulance_phone ? (
                        <a
                          href={`tel:${hospital.ambulance_phone}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Ambulance className="h-4 w-4" />
                          {hospital.ambulance_phone}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Blood Bank
                      </p>

                      {hospital.bloodbank_phone ? (
                        <a
                          href={`tel:${hospital.bloodbank_phone}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Phone className="h-4 w-4" />
                          {hospital.bloodbank_phone}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                  </div>

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Contact Information */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="flex items-center gap-2">
                    <Phone className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Contact Information
                    </h2>
                  </div>

                  <div className="mt-6 grid gap-6 sm:grid-cols-2">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Telephone
                      </p>

                      {hospital.phone ? (
                        <a
                          href={`tel:${hospital.phone}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Phone className="h-4 w-4" />
                          {hospital.phone}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Mobile
                      </p>

                      {hospital.mobile ? (
                        <a
                          href={`tel:${hospital.mobile}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Phone className="h-4 w-4" />
                          {hospital.mobile}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Toll-Free
                      </p>

                      <p className="mt-1">
                        {displayValue(hospital.tollfree)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Helpline
                      </p>

                      <p className="mt-1">
                        {displayValue(hospital.helpline)}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Email
                      </p>

                      {hospital.email ? (
                        <a
                          href={`mailto:${hospital.email}`}
                          className="mt-1 flex items-center gap-2 text-primary hover:underline break-all"
                        >
                          <Mail className="h-4 w-4 shrink-0" />
                          {hospital.email}
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Website
                      </p>

                      {hospital.website ? (
                        <a
                          href={
                            hospital.website.startsWith("http")
                              ? hospital.website
                              : `https://${hospital.website}`
                          }
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-1 flex items-center gap-2 text-primary hover:underline"
                        >
                          <Globe className="h-4 w-4" />
                          Visit hospital website
                        </a>
                      ) : (
                        <p className="mt-1">
                          Not available in directory
                        </p>
                      )}
                    </div>

                  </div>

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Accreditation & Registration */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <div className="flex items-center gap-2">
                    <ShieldCheck className="h-5 w-5 text-primary" />

                    <h2 className="text-lg font-semibold">
                      Registration & Accreditation
                    </h2>
                  </div>

                  <div className="mt-6 grid gap-6 sm:grid-cols-2">

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Accreditation
                      </p>

                      <p className="mt-1">
                        {displayValue(
                          hospital.accreditation
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Registration Number
                      </p>

                      <p className="mt-1">
                        {displayValue(
                          hospital.registration_number
                        )}
                      </p>
                    </div>

                    <div>
                      <p className="text-sm text-muted-foreground">
                        Empanelment / Collaboration
                      </p>

                      <p className="mt-1">
                        {displayValue(
                          hospital.empanelment
                        )}
                      </p>
                    </div>

                  </div>

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Tariff Information */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="p-6">

                  <h2 className="font-semibold">
                    Tariff Information
                  </h2>

                  <p className="mt-2 text-sm text-muted-foreground">
                    {displayValue(hospital.tariff_range)}
                  </p>

                  <p className="mt-3 text-xs text-muted-foreground">
                    Tariff information is based on the available
                    hospital directory data and may not represent
                    the current consultation or treatment cost.
                  </p>

                </CardContent>

              </Card>

              {/* ============================================ */}
              {/* Navigation */}
              {/* ============================================ */}

              <Button
                size="lg"
                className="w-full"
                onClick={handleNavigate}
              >
                <Navigation className="mr-2 h-4 w-4" />
                Navigate to Hospital
              </Button>

            </>
          )}

        </div>
      </main>
    </div>
  );
}