import { useNavigate } from "@tanstack/react-router";
import type { Hospital } from "@/lib/hospital-data";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MapPin, Star, Navigation, Clock } from "lucide-react";

export function HospitalCard({ h }: { h: Hospital }) {
  const navigate = useNavigate();
  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 transition-all hover:-translate-y-0.5 hover:shadow-elevated">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-base font-semibold">
              {h.name}
            </h3>

            <p className="mt-0.5 text-xs text-muted-foreground">
              {h.specialties || "General Medicine"}
            </p>
          </div>

          {h.emergency_available && (
            <Badge className="shrink-0 bg-emergency text-emergency-foreground hover:bg-emergency">
              24/7
            </Badge>
          )}
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5" />
            {h.city}
          </span>

          <span className="flex items-center gap-1">
            <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
            {h.rating ?? "N/A"}
          </span>

          {h.waiting_time !== null && (
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {h.waiting_time} min
            </span>
          )}
        </div>

        <div className="mt-3 text-xs text-muted-foreground">
          Consultation: ₹
          {h.consultation_fee ?? "N/A"}
        </div>

        <div className="mt-4 flex gap-2">
        <Button
          size="sm"
          variant="outline"
          className="flex-1"
          onClick={() => navigate({ to: `/hospital-details/${h.id}` })}
        >
          Details
        </Button>

          <Button
            size="sm"
            className="flex-1 bg-primary hover:bg-primary/90"
          >
            <Navigation className="mr-1 h-3.5 w-3.5" />
            Navigate
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function HospitalCardSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl border border-border/70 bg-card p-5">
      <div className="h-4 w-2/3 rounded bg-muted" />
      <div className="mt-2 h-3 w-1/3 rounded bg-muted" />
      <div className="mt-6 h-3 w-1/2 rounded bg-muted" />

      <div className="mt-4 flex gap-2">
        <div className="h-8 flex-1 rounded bg-muted" />
        <div className="h-8 flex-1 rounded bg-muted" />
      </div>
    </div>
  );
}