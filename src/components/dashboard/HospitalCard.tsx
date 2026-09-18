import { MapPin, Navigation, Phone, BedDouble, Siren } from "lucide-react";
import { useNavigate } from "@tanstack/react-router";

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
};

interface HospitalCardProps {
  hospital: any;
}

export function HospitalCard({ hospital }: HospitalCardProps) {
  const navigate = useNavigate();

  const handleNavigate = () => {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${hospital.latitude},${hospital.longitude}`;
    window.open(url, "_blank");
  };

  const handleDetails = () => {
    navigate({
      to: `/hospital-details/${hospital.id}`,
    });
  };

  return (
    <div className="group rounded-2xl border border-border bg-card p-5 shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-base font-semibold leading-tight text-foreground">
            {hospital.name}
          </h3>

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

      {/* Distance */}
      {hospital.distance_km !== undefined && (
        <div className="mt-4 text-sm font-medium text-foreground">
          {hospital.distance_km.toFixed(2)} km away
        </div>
      )}

      {/* Specialties */}
      {hospital.specialties && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Specialties
          </p>

          <p className="line-clamp-2 text-sm text-foreground">
            {hospital.specialties}
          </p>
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

      {/* Actions */}
      <div className="mt-5 flex gap-2">
        <button
          type="button"
          onClick={handleDetails}
          className="flex-1 rounded-xl border border-border px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          View Details
        </button>

        <button
          type="button"
          onClick={handleNavigate}
          className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Navigation className="h-4 w-4" />
          Navigate
        </button>
      </div>
    </div>
  );
}