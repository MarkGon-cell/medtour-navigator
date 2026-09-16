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
} from "lucide-react";

// ---------------------------------------------------------
// Hospital type returned by FastAPI
// ---------------------------------------------------------

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // -------------------------------------------------------
  // Fetch hospital from FastAPI
  // -------------------------------------------------------

  useEffect(() => {
    const fetchHospital = async () => {
      try {
        setLoading(true);
        setError("");

        const response = await api.get<Hospital>(
          `/hospitals/${hospitalId}`
        );

        setHospital(response.data);
      } catch (err) {
        console.error("Failed to fetch hospital:", err);

        setError("Unable to load hospital details.");
      } finally {
        setLoading(false);
      }
    };

    fetchHospital();
  }, [hospitalId]);

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
        <div className="mx-auto max-w-4xl space-y-6">

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

                    <div>

                      <p className="text-sm text-white/75">
                        Hospital
                      </p>

                      <h1 className="mt-1 text-2xl font-bold sm:text-3xl">
                        {hospital.name}
                      </h1>

                      {/* Location */}
                      <div className="mt-3 flex items-center gap-2 text-sm">

                        <MapPin className="h-4 w-4" />

                        <span>
                          {hospital.city
                            ? `${hospital.city}, `
                            : ""}
                          {hospital.state}
                        </span>

                      </div>

                    </div>

                    {/* Emergency Badge */}
                    {hospital.emergency_available && (
                      <Badge className="bg-emergency text-emergency-foreground">
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

                    <p className="mt-3 text-2xl font-bold">
                      {hospital.total_beds !== null &&
                      hospital.total_beds > 0
                        ? hospital.total_beds
                        : "N/A"}
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

                    <p className="mt-3 text-2xl font-bold">

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

                    <p className="mt-3 text-2xl font-bold">

                      {hospital.specialties
                        ? "Available"
                        : "N/A"}

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

                    <p className="mt-3 text-2xl font-bold">

                      {hospital.pincode || "N/A"}

                    </p>

                    <p className="text-xs text-muted-foreground">
                      PIN Code
                    </p>

                  </CardContent>

                </Card>

              </div>

              {/* ============================================ */}
              {/* Detailed Information */}
              {/* ============================================ */}

              <Card className="rounded-2xl">

                <CardContent className="space-y-6 p-6">

                  {/* ---------------------------------------- */}
                  {/* Address */}
                  {/* ---------------------------------------- */}

                  <div>

                    <h2 className="font-semibold">
                      Address
                    </h2>

                    <p className="mt-1 flex gap-2 text-sm text-muted-foreground">

                      <MapPin className="h-4 w-4 shrink-0" />

                      <span>
                        {hospital.address ||
                          "Address not available"}
                      </span>

                    </p>

                    {hospital.district && (
                      <p className="mt-1 text-sm text-muted-foreground">

                        {hospital.district},{" "}
                        {hospital.state}

                      </p>
                    )}

                  </div>

                  {/* ---------------------------------------- */}
                  {/* Specialties */}
                  {/* ---------------------------------------- */}

                  <div>

                    <h2 className="font-semibold">
                      Specialties
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">

                      {hospital.specialties ||
                        "Not available in directory"}

                    </p>

                  </div>

                  {/* ---------------------------------------- */}
                  {/* Facilities */}
                  {/* ---------------------------------------- */}

                  <div>

                    <h2 className="font-semibold">
                      Facilities
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">

                      {hospital.facilities ||
                        "Not available in directory"}

                    </p>

                  </div>

                  {/* ---------------------------------------- */}
                  {/* Emergency Services */}
                  {/* ---------------------------------------- */}

                  <div>

                    <h2 className="font-semibold">
                      Emergency Services
                    </h2>

                    <div className="mt-2 space-y-2">

                      <div className="flex items-center gap-2">

                        <Ambulance className="h-4 w-4" />

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

                      {hospital.emergency_services && (
                        <p className="text-sm text-muted-foreground">
                          {hospital.emergency_services}
                        </p>
                      )}

                      {hospital.ambulance_phone && (
                        <a
                          href={`tel:${hospital.ambulance_phone}`}
                          className="flex items-center gap-2 text-sm text-primary hover:underline"
                        >
                          <Phone className="h-4 w-4" />

                          Ambulance:{" "}
                          {hospital.ambulance_phone}

                        </a>
                      )}

                    </div>

                  </div>

                  {/* ---------------------------------------- */}
                  {/* Contact */}
                  {/* ---------------------------------------- */}

                  {hospital.phone && (
                    <div>

                      <h2 className="font-semibold">
                        Contact
                      </h2>

                      <a
                        href={`tel:${hospital.phone}`}
                        className="mt-1 flex items-center gap-2 text-sm text-primary hover:underline"
                      >
                        <Phone className="h-4 w-4" />

                        {hospital.phone}

                      </a>

                    </div>
                  )}

                  {/* ---------------------------------------- */}
                  {/* Website */}
                  {/* ---------------------------------------- */}

                  {hospital.website && (
                    <div>

                      <h2 className="font-semibold">
                        Website
                      </h2>

                      <a
                        href={
                          hospital.website.startsWith("http")
                            ? hospital.website
                            : `https://${hospital.website}`
                        }
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-block text-sm text-primary hover:underline"
                      >
                        Visit hospital website
                      </a>

                    </div>
                  )}

                  {/* ---------------------------------------- */}
                  {/* Tariff Information */}
                  {/* ---------------------------------------- */}

                  {hospital.tariff_range && (
                    <div>

                      <h2 className="font-semibold">
                        Tariff Range
                      </h2>

                      <p className="mt-1 text-sm text-muted-foreground">
                        {hospital.tariff_range}
                      </p>

                    </div>
                  )}

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