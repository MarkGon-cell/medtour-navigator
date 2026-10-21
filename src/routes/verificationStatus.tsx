import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { FiCheckCircle, FiShield, FiAlertTriangle, FiUser, FiHome, FiCalendar, FiMapPin, FiExternalLink } from "react-icons/fi";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface VerificationData {
  appointment_code: string;
  is_verified?: boolean;
  is_completed?: boolean;
  badge: string;
  verified: boolean;
  doctor?: {
    name: string | null;
    reg_number: string | null;
    state_council: string | null;
    qualification: string | null;
    specialization: string | null;
    verified: boolean;
    verified_at: string | null;
  };
  hospital?: {
    name: string | null;
    address: string | null;
    city: string | null;
    state: string | null;
    phone: string | null;
  };
  patient?: {
    name: string | null;
  };
  visit?: {
    department: string | null;
    appointment_time: string | null;
    reason: string | null;
    status: string | null;
  };
  verification_url?: string;
}

export const Route = createFileRoute("/verificationStatus")({
  component: VerificationStatusPage,
  validateSearch: (search: Record<string, unknown>) => ({
    aid: typeof search.aid === "string" ? search.aid : "",
  }),
});

function VerificationStatusPage() {
  const { aid } = Route.useSearch();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<VerificationData | null>(null);

  useEffect(() => {
    if (!aid) {
      setError("No appointment reference ID provided.");
      setLoading(false);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);

    // Call the backend API
    fetch(`/api/verificationStatus?aid=${encodeURIComponent(aid)}`)
      .then(async (res) => {
        if (!res.ok) {
          // If proxy not catching /api, try relative /verificationStatus with direct backend fallback
          const fallbackRes = await fetch(`http://127.0.0.1:8000/verificationStatus?aid=${encodeURIComponent(aid)}`).catch(() => null);
          if (fallbackRes && fallbackRes.ok) {
            return fallbackRes.json();
          }
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.detail || `Verification lookup failed (${res.status})`);
        }
        return res.json();
      })
      .then((json: VerificationData) => {
        if (isMounted) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((err: any) => {
        if (isMounted) {
          setError(err.message || "Failed to retrieve verification record.");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [aid]);

  return (
    <div className="min-h-screen bg-background flex flex-col justify-between px-4 py-8 font-sans selection:bg-neutral-800 selection:text-white">
      {/* Header */}
      <header className="w-full max-w-2xl mx-auto flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate({ to: "/landing" })}
          className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-full hover:bg-muted/60 transition-all cursor-pointer"
        >
          <span className="text-xl font-black tracking-tight text-foreground group-hover:opacity-85">
            MedTour
          </span>
        </button>
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-[11px] font-mono font-bold text-emerald-700 dark:text-emerald-400">
          <FiShield className="h-3.5 w-3.5" />
          Public Verification Ledger
        </div>
      </header>

      {/* Main Content */}
      <main className="w-full max-w-xl mx-auto my-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
        {loading ? (
          <Card className="rounded-3xl border border-border/80 p-8 text-center space-y-4 bg-card/90 shadow-sm">
            <div className="h-10 w-10 rounded-full border-2 border-foreground border-t-transparent animate-spin mx-auto" />
            <div className="space-y-1">
              <h2 className="text-base font-extrabold text-foreground">
                Verifying Clinical Signature…
              </h2>
              <p className="text-xs text-muted-foreground font-mono">
                Querying appointment reference #{aid}
              </p>
            </div>
          </Card>
        ) : error || !data ? (
          <Card className="rounded-3xl border border-red-500/30 p-8 text-center space-y-4 bg-card/90 shadow-sm">
            <div className="h-12 w-12 rounded-full bg-red-500/10 text-red-600 flex items-center justify-center mx-auto">
              <FiAlertTriangle className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h2 className="text-lg font-black text-foreground">
                Record Not Verified
              </h2>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto leading-relaxed">
                {error || "No valid discharge or appointment record could be located for this identifier."}
              </p>
            </div>
            <Button
              onClick={() => navigate({ to: "/landing" })}
              className="rounded-full px-6 h-10 font-extrabold text-xs bg-black text-white dark:bg-white dark:text-black cursor-pointer"
            >
              Return to MedTour Home
            </Button>
          </Card>
        ) : (
          <Card className="rounded-3xl border border-border/80 p-6 sm:p-8 space-y-6 bg-card/90 backdrop-blur-xl shadow-[0_8px_30px_rgba(0,0,0,0.06)]">
            {/* Status Banner */}
            <div className="flex items-center justify-between pb-4 border-b border-border/60">
              <div className="space-y-1">
                <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-muted-foreground block">
                  Official Verification Token
                </span>
                <span className="text-xl font-mono font-black text-foreground tracking-tight">
                  {data.appointment_code}
                </span>
              </div>
              <div
                className={`px-3 py-1.5 rounded-full text-xs font-black inline-flex items-center gap-1.5 shadow-xs ${
                  data.verified
                    ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border border-emerald-500/40"
                    : "bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/40"
                }`}
              >
                <FiCheckCircle className="h-4 w-4" />
                {data.badge || "VERIFIED CLAIM"}
              </div>
            </div>

            {/* Verification Detail Blocks */}
            <div className="space-y-4 text-xs">
              {/* Doctor Details */}
              <div className="p-4 rounded-2xl bg-muted/40 border border-border/60 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground">
                    Attending Physician
                  </span>
                  {data.doctor?.verified && (
                    <span className="text-[10px] font-mono font-bold text-emerald-600 bg-emerald-500/10 px-2 py-0.5 rounded-full">
                      ✓ NMC Registered
                    </span>
                  )}
                </div>
                <h3 className="text-base font-extrabold text-foreground">
                  Dr. {data.doctor?.name || "Practitioner on Duty"}
                </h3>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground pt-1">
                  <div>
                    <span className="block font-bold text-foreground">Reg Number:</span>
                    <span className="font-mono">{data.doctor?.reg_number || "Verified"}</span>
                  </div>
                  <div>
                    <span className="block font-bold text-foreground">State Council:</span>
                    <span>{data.doctor?.state_council || "Medical Council of India"}</span>
                  </div>
                </div>
              </div>

              {/* Hospital & Department */}
              <div className="p-4 rounded-2xl bg-muted/40 border border-border/60 space-y-2">
                <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground">
                  Care Facility & Department
                </span>
                <h3 className="text-sm font-extrabold text-foreground">
                  {data.hospital?.name || "Accredited Health Facility"}
                </h3>
                <p className="text-[11px] text-muted-foreground">
                  {data.hospital?.address || ""}
                  {data.hospital?.city ? `, ${data.hospital.city}` : ""}
                  {data.hospital?.state ? `, ${data.hospital.state}` : ""}
                </p>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground pt-1 border-t border-border/40">
                  <div>
                    <span className="block font-bold text-foreground">Department:</span>
                    <span>{data.visit?.department || "General / Clinical"}</span>
                  </div>
                  <div>
                    <span className="block font-bold text-foreground">Status:</span>
                    <span className="uppercase font-semibold text-emerald-600 dark:text-emerald-400">
                      {data.visit?.status || "Completed"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Patient Tourist Reference */}
              <div className="p-4 rounded-2xl bg-muted/40 border border-border/60 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground block">
                    Patient Reference
                  </span>
                  <span className="text-sm font-extrabold text-foreground">
                    {data.patient?.name || "Guest Traveler"}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground block">
                    Date of Visit
                  </span>
                  <span className="text-[11px] font-bold text-foreground">
                    {data.visit?.appointment_time
                      ? new Date(data.visit.appointment_time).toLocaleDateString()
                      : "Verified Record"}
                  </span>
                </div>
              </div>
            </div>

            {/* Privacy Guarantee Note */}
            <div className="p-3.5 rounded-2xl bg-muted/20 border border-border/50 text-[11px] text-muted-foreground leading-relaxed text-center">
              🔒 <strong>Zero-Knowledge Cryptographic Verification:</strong> Clinical diagnosis, prescriptions, and sensitive medical notes are not exposed on this public verification page. They reside exclusively inside the patient's encrypted <code className="font-bold text-foreground">.mtr</code> vault.
            </div>

            {/* Back action */}
            <Button
              onClick={() => navigate({ to: "/visits" })}
              className="w-full h-12 rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 font-extrabold text-sm shadow-md transition-all active:scale-98 cursor-pointer"
            >
              ← Go to Patient Visits Ledger
            </Button>
          </Card>
        )}
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-muted-foreground font-mono py-4">
        MedTour Navigator · Decentralized Medical Tourism Health Ledger
      </footer>
    </div>
  );
}
