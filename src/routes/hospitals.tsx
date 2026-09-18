import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Search,
  MapPin,
  SlidersHorizontal,
  AlertCircle,
  Hospital as HospitalIcon,
} from "lucide-react";

import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { HospitalCard } from "@/components/dashboard/HospitalCard";
import api from "@/lib/api";

export const Route = createFileRoute("/hospitals")({
  component: HospitalsPage,
});

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
  distance_km: number;
};

function HospitalsPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [radius, setRadius] = useState(10);
  const [search, setSearch] = useState("");
  const [emergency, setEmergency] = useState(false);

  useEffect(() => {
    if (!navigator.geolocation) {
      setError("Location services are not supported by this browser.");
      setLoading(false);
      return;
    }

    setLoading(true);
    setError("");

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;

          console.log("Hospital search location:", {
            latitude,
            longitude,
          });

          const response = await api.get<Hospital[]>(
            "/hospitals/nearby",
            {
              params: {
                latitude,
                longitude,
                radius_km: radius,
                emergency,
              },
            }
          );

          setHospitals(response.data);
        } catch (err) {
          console.error(err);
          setError("Unable to load nearby hospitals.");
        } finally {
          setLoading(false);
        }
      },
      (err) => {
        console.error(err);
        setError(
          "Location permission is required to find nearby hospitals."
        );
        setLoading(false);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  }, [radius, emergency]);

  const filteredHospitals = hospitals.filter((hospital) =>
    hospital.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex min-h-screen bg-background">
      <DashboardSidebar />

      <main className="min-w-0 flex-1">
        {/* Page Header */}
        <div className="border-b border-border bg-card">
          <div className="px-6 py-6 lg:px-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary">
                    <HospitalIcon className="h-5 w-5" />
                  </div>

                  <div>
                    <h1 className="text-2xl font-bold tracking-tight text-foreground">
                      Hospitals Near You
                    </h1>

                    <div className="mt-1 flex items-center gap-1.5 text-sm text-muted-foreground">
                      <MapPin className="h-3.5 w-3.5" />
                      <span>
                        Find healthcare providers based on your current
                        location
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded-xl bg-primary/5 px-4 py-2.5 text-sm">
                <span className="font-medium text-primary">
                  {filteredHospitals.length}
                </span>{" "}
                <span className="text-muted-foreground">
                  hospitals found
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="px-6 py-6 lg:px-8">
          {/* Filters */}
          <div className="mb-6 rounded-2xl border border-border bg-card p-4 shadow-soft">
            <div className="mb-4 flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-primary" />

              <h2 className="text-sm font-semibold text-foreground">
                Find a Hospital
              </h2>
            </div>

            <div className="grid gap-3 md:grid-cols-[1fr_auto_auto]">
              {/* Search */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                <input
                  type="text"
                  placeholder="Search hospital by name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="h-11 w-full rounded-xl border border-border bg-background pl-10 pr-4 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </div>

              {/* Radius */}
              <select
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                className="h-11 rounded-xl border border-border bg-background px-4 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20"
              >
                <option value={5}>Within 5 km</option>
                <option value={10}>Within 10 km</option>
                <option value={20}>Within 20 km</option>
              </select>

              {/* Emergency */}
              <label
                className={`flex h-11 cursor-pointer items-center gap-2 rounded-xl border px-4 text-sm font-medium transition-colors ${
                  emergency
                    ? "border-destructive/30 bg-destructive/10 text-destructive"
                    : "border-border bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                <input
                  type="checkbox"
                  checked={emergency}
                  onChange={(e) => setEmergency(e.target.checked)}
                  className="h-4 w-4 accent-primary"
                />

                <AlertCircle className="h-4 w-4" />

                <span>Emergency only</span>
              </label>
            </div>
          </div>

          {/* Loading */}
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  className="h-80 animate-pulse rounded-2xl border border-border bg-card"
                />
              ))}
            </div>
          ) : error ? (
            <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-destructive/20 bg-destructive/5 p-8 text-center">
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-destructive/10 text-destructive">
                <AlertCircle className="h-6 w-6" />
              </div>

              <h2 className="font-semibold text-foreground">
                Unable to find hospitals
              </h2>

              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                {error}
              </p>
            </div>
          ) : filteredHospitals.length === 0 ? (
            <div className="flex min-h-64 flex-col items-center justify-center rounded-2xl border border-border bg-card p-8 text-center">
              <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-muted text-muted-foreground">
                <HospitalIcon className="h-6 w-6" />
              </div>

              <h2 className="font-semibold text-foreground">
                No hospitals found
              </h2>

              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Try increasing the search radius or changing your search
                term.
              </p>
            </div>
          ) : (
            <>
              {/* Results heading */}
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">
                    Nearby Hospitals
                  </h2>

                  <p className="text-sm text-muted-foreground">
                    Showing hospitals within {radius} km of your location
                  </p>
                </div>
              </div>

              {/* Hospital Cards */}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {filteredHospitals.map((hospital) => (
                  <HospitalCard
                    key={hospital.id}
                    hospital={hospital}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}