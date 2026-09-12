import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import api from "@/lib/api";
import type { Hospital } from "@/lib/hospital-data";

import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

import {
  ArrowLeft,
  MapPin,
  Star,
  Clock,
  Phone,
  Languages,
  Stethoscope,
  Ambulance,
  Bed,
  Navigation,
} from "lucide-react";

export const Route = createFileRoute("/hospital-details/$hospitalId")({
  component: HospitalDetails,
});

function HospitalDetails() {
  const { hospitalId } = Route.useParams();

  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchHospital = async () => {
      try {
        setLoading(true);

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

  const handleNavigate = () => {
    if (!hospital) return;

    window.open(
      `https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}`,
      "_blank"
    );
  };

  return (
    <div className="flex min-h-screen bg-muted/30">
      <DashboardSidebar />

      <main className="flex-1 p-4 sm:p-6">
        <div className="mx-auto max-w-4xl space-y-6">

          <Button
            variant="ghost"
            onClick={() => window.history.back()}
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Dashboard
          </Button>

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

          {!loading && error && (
            <Card className="rounded-2xl">
              <CardContent className="p-8 text-center">
                <p className="text-sm text-destructive">
                  {error}
                </p>
              </CardContent>
            </Card>
          )}

          {!loading && hospital && (
            <>
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

                      <div className="mt-3 flex items-center gap-2 text-sm">
                        <MapPin className="h-4 w-4" />
                        {hospital.city}, {hospital.state}
                      </div>
                    </div>

                    {hospital.emergency_available && (
                      <Badge className="bg-emergency text-emergency-foreground">
                        24/7 Emergency
                      </Badge>
                    )}
                  </div>
                </div>
              </Card>

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

                <Card className="rounded-2xl">
                  <CardContent className="p-5">
                    <Star className="h-5 w-5 text-amber-500" />
                    <p className="mt-3 text-2xl font-bold">
                      {hospital.rating ?? "N/A"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Rating
                    </p>
                  </CardContent>
                </Card>

                <Card className="rounded-2xl">
                  <CardContent className="p-5">
                    <Clock className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-2xl font-bold">
                      {hospital.waiting_time ?? "N/A"}
                      {hospital.waiting_time !== null && " min"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Waiting Time
                    </p>
                  </CardContent>
                </Card>

                <Card className="rounded-2xl">
                  <CardContent className="p-5">
                    <Stethoscope className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-2xl font-bold">
                      ₹{hospital.consultation_fee ?? "N/A"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Consultation Fee
                    </p>
                  </CardContent>
                </Card>

                <Card className="rounded-2xl">
                  <CardContent className="p-5">
                    <Bed className="h-5 w-5 text-primary" />
                    <p className="mt-3 text-2xl font-bold">
                      {hospital.icu_available
                        ? "Available"
                        : "No"}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      ICU Facility
                    </p>
                  </CardContent>
                </Card>

              </div>

              <Card className="rounded-2xl">
                <CardContent className="space-y-6 p-6">

                  <div>
                    <h2 className="font-semibold">
                      Address
                    </h2>

                    <p className="mt-1 flex gap-2 text-sm text-muted-foreground">
                      <MapPin className="h-4 w-4 shrink-0" />
                      {hospital.address}
                    </p>
                  </div>

                  <div>
                    <h2 className="font-semibold">
                      Specialties
                    </h2>

                    <p className="mt-1 text-sm text-muted-foreground">
                      {hospital.specialties || "General Medicine"}
                    </p>
                  </div>

                  <div>
                    <h2 className="font-semibold">
                      Languages
                    </h2>

                    <p className="mt-1 flex gap-2 text-sm text-muted-foreground">
                      <Languages className="h-4 w-4" />
                      {hospital.languages || "English"}
                    </p>
                  </div>

                  <div>
                    <h2 className="font-semibold">
                      Emergency Services
                    </h2>

                    <div className="mt-2 flex items-center gap-2">
                      <Ambulance className="h-4 w-4" />

                      {hospital.emergency_available ? (
                        <Badge>
                          Emergency Available
                        </Badge>
                      ) : (
                        <Badge variant="outline">
                          Emergency Not Available
                        </Badge>
                      )}
                    </div>
                  </div>

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

                </CardContent>
              </Card>

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