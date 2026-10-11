import { useEffect, useRef, useState } from "react";
import { AlertCircle, ExternalLink, Loader2, Sparkles } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import api from "@/lib/api";

export type AiHospital = {
  name: string;
  city?: string | null;
  state?: string | null;
  address?: string | null;
  phone?: string | null;
  specialties?: string | null;
  facilities?: string | null;
  totalBeds?: number | null;
  accreditation?: string | null;
  rating?: number | null;
  reviewCount?: number | null;
  curability?: string | null;
  aiMatchReason?: string | null;
  distanceKm?: number | null;
};

type HospitalDbInfo = {
  id?: number;
  name?: string;
  address?: string;
  city?: string;
  state?: string;
  phone?: string;
  emergency_available?: boolean;
  specialties?: string;
  facilities?: string;
  total_beds?: number;
  doctors?: number;
  accreditation?: string;
  established_year?: number;
  rating?: number;
  review_count?: number;
};

type NimSummary = {
  overview?: string;
  key_departments?: string[];
  emergency_and_wait?: string;
  patient_amenities?: string;
  verdict?: string;
};

type AiSearchResponse = {
  query: string;
  status: "ok" | "limit" | "link" | "blocked" | "unparsed";
  answer: string;
  sources: { title: string; url: string }[];
  search_url: string;
  detail?: string;
  hospital_db_info?: HospitalDbInfo | null;
  nim_summary?: NimSummary | null;
  usage: { limit: number; used: number; remaining: number; date: string };
};

type Phase = "loading" | "ok" | "degraded" | "error";

interface HospitalAiDialogProps {
  /** Null closes the dialog. Non-null triggers the AI search for that row. */
  hospital: AiHospital | null;
  onClose: () => void;
}

/** Same query the backend would run, so the fallback link matches exactly. */
export function aiModeUrl(query: string): string {
  return `https://aimode.google.com/search?q=${encodeURIComponent(query)}`;
}

/**
 * "More info about this hospital" from Google AI Mode, opened by clicking a
 * hospital card.
 *
 * Backed by GET /ai/google-search, which is capped at 2 uses per user per
 * day and never fabricates an answer: when Google cannot be reached from
 * the server (or the allowance is spent) it hands back a deep link, and this
 * dialog opens that link in the user's own browser instead.
 */
export function HospitalAiDialog({ hospital, onClose }: HospitalAiDialogProps) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [data, setData] = useState<AiSearchResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  // True when the query was handed to a freshly opened Google AI Mode tab.
  const [handedOff, setHandedOff] = useState(false);

  // A card can be re-clicked while a previous request is in flight; only the
  // latest one is allowed to write state.
  const requestSeq = useRef(0);

  const query = hospital
    ? [hospital.name, hospital.city, hospital.state].filter(Boolean).join(" ")
    : "";
  const open = Boolean(hospital);

  // Dependencies are primitives on purpose: the caller rebuilds the
  // `hospital` object on every render, and re-running this effect would
  // spend the daily AI allowance once per keystroke in a parent search box.
  useEffect(() => {
    if (!open || !query) return;

    const sequence = ++requestSeq.current;
    setPhase("loading");
    setData(null);
    setErrorMessage("");
    setHandedOff(false);

    api
      .get<AiSearchResponse>("/ai/google-search", { params: { q: query } })
      .then((response) => {
        if (sequence !== requestSeq.current) return;

        const payload = response.data;
        setData(payload);
        setPhase(payload.status === "ok" ? "ok" : "degraded");

        // Server-side answer unavailable (no GOOGLE_AI_* session on the
        // backend, or today's 2 answers spent). The user's own browser has
        // a live Google session, so hand the same query straight to it --
        // still inside the click's transient activation, so the popup is
        // allowed. If the browser blocks it, the button below is the retry.
        if (payload.status === "link" || payload.status === "limit") {
          // `noopener` in the feature string would make window.open return
          // null *even on success*, so open first, then sever the opener --
          // that keeps `handedOff` honest about whether a tab appeared.
          const opened = window.open(payload.search_url, "_blank");
          if (opened) {
            opened.opener = null;
          }
          setHandedOff(Boolean(opened));
        }
      })
      .catch((error) => {
        if (sequence !== requestSeq.current) return;

        const detail = error?.response?.data?.detail;
        setErrorMessage(
          typeof detail === "string"
            ? detail
            : (detail?.message ?? "Google AI could not be reached right now.")
        );
        setPhase("error");
      });
  }, [open, query]);

  const searchUrl = data?.search_url || aiModeUrl(query);
  const usage = data?.usage;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary/10 text-primary">
              <Sparkles className="h-4 w-4" />
            </span>
            Google AI Overview
          </DialogTitle>

          <DialogDescription className="break-words">
            {query || "Hospital"}
          </DialogDescription>
        </DialogHeader>

        {/* Daily allowance banner with Add More Uses option */}
        {usage && (
          <div className="rounded-xl bg-muted/60 p-2.5 text-xs font-medium text-muted-foreground flex flex-col sm:flex-row sm:items-center justify-between gap-2 border border-border/70">
            <div>
              <span className="font-extrabold text-foreground">{usage.remaining} of {usage.limit}</span> free AI queries left today.
              {usage.remaining === 0 && " Resets at midnight."}
            </div>
            <button
              onClick={() => {
                alert("Simulated Payment Gateway: Pay ₹49 ($0.59) for 10 Instant AI Deep Analysis Queries. (Payment integrated in demo mode).");
              }}
              className="text-[11px] font-black px-2.5 py-1 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary transition-colors text-center shrink-0 border border-primary/20"
            >
              + Get More AI Uses (₹49)
            </button>
          </div>
        )}

        {/* Verified Hospital DB Information Block */}
        {(hospital?.address || hospital?.specialties || hospital?.facilities || data?.hospital_db_info) && (
          <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase tracking-wider text-primary flex items-center gap-1.5">
                🏛️ Hospital Database Profile
              </span>
              {(hospital?.rating != null || data?.hospital_db_info?.rating != null) && (
                <span className="text-xs font-bold text-amber-600 dark:text-amber-400">
                  ★ {(hospital?.rating || data?.hospital_db_info?.rating)?.toFixed(1)} Rating
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground font-semibold block text-[11px]">Address & City:</span>
                <span className="font-bold text-foreground">
                  {hospital?.address || data?.hospital_db_info?.address || hospital?.city || "Standard Local Area"}
                </span>
              </div>
              <div>
                <span className="text-muted-foreground font-semibold block text-[11px]">Emergency Ward & Phone:</span>
                <span className="font-bold text-foreground">
                  {hospital?.phone || data?.hospital_db_info?.phone || "24/7 Desk Verified"}
                </span>
              </div>
              {(hospital?.specialties || data?.hospital_db_info?.specialties) && (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground font-semibold block text-[11px]">Specialties & Departments:</span>
                  <span className="font-medium text-foreground">
                    {hospital?.specialties || data?.hospital_db_info?.specialties}
                  </span>
                </div>
              )}
              {(hospital?.facilities || data?.hospital_db_info?.facilities) && (
                <div className="sm:col-span-2">
                  <span className="text-muted-foreground font-semibold block text-[11px]">Key Facilities & Beds:</span>
                  <span className="font-medium text-foreground">
                    {hospital?.facilities || data?.hospital_db_info?.facilities}
                    {(hospital?.totalBeds || data?.hospital_db_info?.total_beds) ? ` (${hospital?.totalBeds || data?.hospital_db_info?.total_beds} Total Beds)` : ""}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Skeleton Loading State */}
        {phase === "loading" && (
          <div className="space-y-3 p-4 rounded-2xl border border-border/80 bg-muted/20 animate-pulse">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span className="text-xs font-bold text-muted-foreground">
                Analyzing Hospital with Nvidia NIM & Google AI...
              </span>
            </div>
            <div className="h-4 bg-muted rounded-md w-3/4"></div>
            <div className="h-3 bg-muted rounded-md w-full"></div>
            <div className="h-3 bg-muted rounded-md w-5/6"></div>
            <div className="grid grid-cols-2 gap-2 pt-2">
              <div className="h-14 bg-muted rounded-xl"></div>
              <div className="h-14 bg-muted rounded-xl"></div>
            </div>
          </div>
        )}

        {/* Nvidia NIM Readable Synthesized Layout */}
        {data?.nim_summary && (
          <div className="rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-4 space-y-3 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
                ⚡ Nvidia NIM Clinical Synthesis
              </span>
              <span className="text-[10px] font-bold text-muted-foreground">
                AI Verified
              </span>
            </div>

            <p className="text-sm font-semibold text-foreground leading-relaxed">
              {data.nim_summary.overview}
            </p>

            {data.nim_summary.key_departments && data.nim_summary.key_departments.length > 0 && (
              <div>
                <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wide block mb-1">
                  Key Departments:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {data.nim_summary.key_departments.map((dept, i) => (
                    <span key={i} className="text-[11px] font-extrabold px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300">
                      {dept}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
              <div className="p-2.5 rounded-xl bg-background/80 border border-border">
                <span className="text-[11px] font-bold text-muted-foreground block mb-0.5">🚨 Emergency & Dispatch</span>
                <span className="font-semibold text-foreground leading-snug">{data.nim_summary.emergency_and_wait}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-background/80 border border-border">
                <span className="text-[11px] font-bold text-muted-foreground block mb-0.5">🏥 Patient Amenities</span>
                <span className="font-semibold text-foreground leading-snug">{data.nim_summary.patient_amenities}</span>
              </div>
            </div>

            {data.nim_summary.verdict && (
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs font-bold text-emerald-800 dark:text-emerald-300">
                💡 <span className="font-extrabold">Recommendation:</span> {data.nim_summary.verdict}
              </div>
            )}
          </div>
        )}

        {phase === "ok" && data && !data.nim_summary && (
          <>
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground">
              {data.answer}
            </p>

            {data.sources.length > 0 && (
              <div className="mt-2">
                <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-muted-foreground">
                  Sources
                </p>

                <div className="flex flex-col gap-1">
                  {data.sources.map((source) => (
                    <a
                      key={source.url}
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="truncate text-xs text-primary underline-offset-2 hover:underline"
                    >
                      {source.title}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {phase === "degraded" && data && (
          <div className="rounded-xl border border-border bg-muted/40 px-4 py-4 text-sm text-muted-foreground">
            {handedOff ? (
              data.status === "limit" ? (
                <>
                  <span className="font-medium text-foreground">
                    Google AI Mode opened in a new tab.
                  </span>{" "}
                  Today's in-app allowance is used up, so the same query is
                  running there instead — it does not count against your cap.
                </>
              ) : (
                <>
                  <span className="font-medium text-foreground">
                    Google AI Mode opened in a new tab.
                  </span>{" "}
                  The full overview for this hospital is loading there.
                </>
              )
            ) : (
              (data.detail ||
                "Google did not return a readable AI answer from the server.")
            )}
          </div>
        )}

        {phase === "error" && (
          <div className="flex items-start gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* One escape hatch for every non-OK state: the same query, opened
            in the user's browser where their Google session lives. */}
        {phase !== "ok" && phase !== "loading" && (
          <a
            href={searchUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <ExternalLink className="h-4 w-4" />
            Open this search on Google
          </a>
        )}
      </DialogContent>
    </Dialog>
  );
}
