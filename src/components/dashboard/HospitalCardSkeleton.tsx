import { Skeleton } from "@/components/ui/skeleton";

export function HospitalCardSkeleton() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-soft space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 flex-1">
          <div className="flex items-center gap-2">
            <Skeleton className="h-5 w-48 rounded-md" />
            <Skeleton className="h-5 w-24 rounded-full" />
          </div>
          <Skeleton className="h-4 w-36 rounded-md" />
        </div>
        <Skeleton className="h-6 w-20 rounded-full" />
      </div>

      {/* AI match reason banner skeleton */}
      <Skeleton className="h-8 w-full rounded-xl" />

      {/* Distance skeleton */}
      <Skeleton className="h-4 w-28 rounded-md" />

      {/* Specialties badges skeleton */}
      <div className="space-y-1.5">
        <Skeleton className="h-3 w-20 rounded-md" />
        <div className="flex flex-wrap gap-1.5">
          <Skeleton className="h-6 w-20 rounded-lg" />
          <Skeleton className="h-6 w-24 rounded-lg" />
          <Skeleton className="h-6 w-16 rounded-lg" />
          <Skeleton className="h-6 w-28 rounded-lg" />
        </div>
      </div>

      {/* Info grid */}
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-16 rounded-xl" />
        <Skeleton className="h-16 rounded-xl" />
      </div>

      {/* Address */}
      <Skeleton className="h-4 w-3/4 rounded-md" />

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <Skeleton className="h-10 flex-1 rounded-xl" />
        <Skeleton className="h-10 flex-1 rounded-xl" />
      </div>
    </div>
  );
}
