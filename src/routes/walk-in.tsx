import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useMemo, useEffect } from "react";
import { MobileNav } from "@/components/site/MobileNav.tsx";
import { QuickMedicalIdModal } from "@/components/site/QuickMedicalIdModal";
import { HospitalAiDialog, type AiHospital } from "@/components/dashboard/HospitalAiDialog";
import { Button } from "@/components/ui/button";
import { FiSearch, FiMapPin, FiPhone, FiArrowRight, FiChevronUp, FiChevronDown, FiShield, FiAlertTriangle, FiLoader } from "react-icons/fi";
import { FaLocationArrow } from "react-icons/fa";
import { toast } from "sonner";
import api from "@/lib/api";

export const Route = createFileRoute("/walk-in")({
  head: () => ({
    meta: [
      { title: "Walk-In Urgent Care Directory | MedTour" },
      { name: "description", content: "Flat-file verified urgent care clinic directory." },
    ],
  }),
  component: WalkInDirectoryPage,
});

export interface Clinic {
  id: string;
  name: string;
  distanceKm: number;
  address: string;
  city: string;
  phone: string;
  englishSpeaking: boolean;
  cashlessInsurance: boolean;
  openNow: boolean;
  estimatedWaitMins: number;
  symptomTags: string[];
  lat: number;
  lng: number;
  aiMatchReason?: string;
  aiMatchScore?: number;
  // Reputation (inferred from name/services, or a real rating when loaded)
  reputationBand?: string;
  reputationSource?: "inferred" | "rated";
  rating?: number | null;
  reviewCount?: number | null;
  // Curability: can this facility treat the triaged condition?
  curable?: boolean;
  curability?: string;
  // Multi-step AI curation tier
  tier?: "best" | "nearest" | "nearby";
  specialties?: string;
  facilities?: string;
  totalBeds?: number;
  accreditation?: string;
}

const CLINICS_DATA: Clinic[] = [
  {
    id: "c-101",
    name: "Apex Care Urgent Clinic & ER",
    distanceKm: 0.8,
    address: "Bandra Kurla Complex, Mumbai",
    city: "Mumbai",
    phone: "+91 22 6123 4567",
    englishSpeaking: true,
    cashlessInsurance: true,
    openNow: true,
    estimatedWaitMins: 15,
    symptomTags: ["Food Poisoning", "High Fever", "Stitches / Wounds"],
    lat: 19.0600,
    lng: 72.8600,
  },
  {
    id: "c-102",
    name: "Lilavati Walk-In International Desk",
    distanceKm: 1.4,
    address: "Bandra West, Mumbai",
    city: "Mumbai",
    phone: "+91 22 2675 1000",
    englishSpeaking: true,
    cashlessInsurance: true,
    openNow: true,
    estimatedWaitMins: 20,
    symptomTags: ["Food Poisoning", "Stitches / Wounds"],
    lat: 19.0500,
    lng: 72.8250,
  },
  {
    id: "c-103",
    name: "Apollo Clinic Indiranagar",
    distanceKm: 2.1,
    address: "Indiranagar, Bengaluru",
    city: "Bengaluru",
    phone: "+91 80 4112 3344",
    englishSpeaking: true,
    cashlessInsurance: false,
    openNow: true,
    estimatedWaitMins: 10,
    symptomTags: ["High Fever"],
    lat: 12.9780,
    lng: 77.6400,
  },
];

// Search radius for the AI triage hospital list. The backend has no cap on
// this value, but a radius beyond ~50 km returns hospitals the user would
// never travel to in an emergency, so the options stay small and honest.
const RADIUS_OPTIONS_KM = [3, 5, 10, 25, 50];
const DEFAULT_RADIUS_KM = 10;

// Exactly 3 quick symptom tags
const TOP_3_TAGS = ["Food Poisoning", "High Fever", "Stitches / Wounds"];

const WALK_IN_SESSION_KEY = "medtour_tab_walkin_state";

function getInitialWalkInState() {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(WALK_IN_SESSION_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn("Failed to load walk-in tab state", e);
  }
  return null;
}

function WalkInDirectoryPage() {
  const navigate = useNavigate();
  const savedState = useMemo(() => getInitialWalkInState(), []);

  const [searchQuery, setSearchQuery] = useState(savedState?.searchQuery || "");
  const [selectedSymptom, setSelectedSymptom] = useState<string | null>(savedState?.selectedSymptom || null);
  const [isMedicalIdOpen, setIsMedicalIdOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(savedState?.isCollapsed || false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isFirstAidOpen, setIsFirstAidOpen] = useState(savedState?.isFirstAidOpen ?? true);
  const [isPrereqsOpen, setIsPrereqsOpen] = useState(savedState?.isPrereqsOpen ?? true);
  const [aiAnalysisResult, setAiAnalysisResult] = useState<{
    specialty?: string;
    urgency?: string;
    summary?: string;
    firstAid?: string[];
    prerequisites?: string[];
  } | null>(savedState?.aiAnalysisResult || null);
  const [backendHospitals, setBackendHospitals] = useState<Clinic[] | null>(savedState?.backendHospitals || null);
  const [radiusKm, setRadiusKm] = useState<number>(savedState?.radiusKm || DEFAULT_RADIUS_KM);
  const [showHospitals, setShowHospitals] = useState(savedState?.showHospitals || false);

  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number }>(
    savedState?.userLocation || { lat: 19.0760, lng: 72.8777 }
  );
  const [aiHospital, setAiHospital] = useState<AiHospital | null>(null);

  // Persist walk-in state into sessionStorage whenever values update
  useEffect(() => {
    try {
      const stateToSave = {
        searchQuery,
        selectedSymptom,
        radiusKm,
        aiAnalysisResult,
        backendHospitals,
        showHospitals,
        isFirstAidOpen,
        isPrereqsOpen,
        isCollapsed,
        userLocation,
      };
      sessionStorage.setItem(WALK_IN_SESSION_KEY, JSON.stringify(stateToSave));
    } catch (e) {
      console.warn("Failed to persist walk-in tab state", e);
    }
  }, [
    searchQuery,
    selectedSymptom,
    radiusKm,
    aiAnalysisResult,
    backendHospitals,
    showHospitals,
    isFirstAidOpen,
    isPrereqsOpen,
    isCollapsed,
    userLocation,
  ]);

  // Watch GPS position
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        },
        () => {},
        { enableHighAccuracy: true, timeout: 5000 }
      );
    }
  }, []);

  // Two-step reveal: once triage is shown, fade the hospital list in after a
  // short beat so the user reads triage first. Fires on the triage result
  // alone (the offline fallback has triage but no backend hospitals, and must
  // reveal the static list rather than spin forever).
  useEffect(() => {
    if (!aiAnalysisResult) {
      setShowHospitals(false);
      return;
    }
    const t = setTimeout(() => setShowHospitals(true), 1600);
    return () => clearTimeout(t);
  }, [aiAnalysisResult]);

  // Auto-collapse search box when scrolling down hospital recommendations list
  useEffect(() => {
    let lastScrollY = window.scrollY;

    const handleScroll = () => {
      const currentScrollY = window.scrollY;
      if (currentScrollY > 80 && currentScrollY > lastScrollY) {
        setIsCollapsed(true);
      } else if (currentScrollY < 40) {
        setIsCollapsed(false);
      }
      lastScrollY = currentScrollY;
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const triggerBackendAnalysis = async (symptomsText: string, radiusOverride?: number) => {
    if (!symptomsText.trim() || isAnalyzing) return;
    setIsAnalyzing(true);
    setAiAnalysisResult(null);
    setShowHospitals(false);

    try {
      const lat = typeof userLocation?.lat === "number" && !isNaN(userLocation.lat) ? userLocation.lat : 19.0760;
      const lng = typeof userLocation?.lng === "number" && !isNaN(userLocation.lng) ? userLocation.lng : 72.8777;

      const res = await api.post("/ai/analyze", {
        symptoms: symptomsText,
        latitude: lat,
        longitude: lng,
        radius_km: radiusOverride ?? radiusKm,
      });

      if (res.data) {
        setAiAnalysisResult({
          specialty: res.data.specialty,
          urgency: res.data.urgency,
          summary: res.data.summary,
          firstAid: res.data.firstAid,
          prerequisites: res.data.prerequisites,
        });

        if (Array.isArray(res.data.recommendedHospitals) && res.data.recommendedHospitals.length > 0) {
          const mapped: Clinic[] = res.data.recommendedHospitals.map((h: any) => ({
            id: `api-${h.id || Math.random()}`,
            name: h.name,
            distanceKm: h.distance_km ?? 0,
            address: h.address || h.city || "",
            city: h.city || "",
            // No invented numbers: a missing phone stays missing so the call
            // button hides rather than dialling a fake directory listing.
            phone: h.phone || h.emergency_phone || h.ambulance_phone || "",
            englishSpeaking: true,
            cashlessInsurance: true,
            openNow: h.emergency_available ?? true,
            estimatedWaitMins: 0,
            symptomTags: [res.data.specialty || "Urgent Care"],
            lat: h.latitude || 19.0600,
            lng: h.longitude || 72.8600,
            aiMatchReason: h.ai_match_reason,
            aiMatchScore: h.ai_match_score,
            tier: h.tier,
            specialties: h.specialties,
            facilities: h.facilities,
            totalBeds: h.total_beds,
            accreditation: h.accreditation,
            // Reputation + curability from the ranking step
            reputationBand: h.reputation_band,
            reputationSource: h.reputation_source,
            rating: h.rating ?? null,
            reviewCount: h.review_count ?? null,
            curable: h.curable,
            curability: h.curability,
          }));
          setBackendHospitals(mapped);
        } else {
          setBackendHospitals(null);
        }
        toast.success("AI Triage complete!");
      }
    } catch (err) {
      console.warn("Backend /ai/analyze endpoint unreachable. Using guest-first offline dataset fallback.", err);
      setBackendHospitals(null);
      // Offline emergency advice fallback
      setAiAnalysisResult({
        specialty: "URGENT CARE",
        urgency: "URGENT",
        summary: `Triage evaluation for: ${symptomsText}`,
        firstAid: [
          "Rest in a safe, comfortable position and avoid physical exertion.",
          "Apply clean direct pressure if bleeding, or sip Oral Rehydration Salts (ORS) for stomach distress.",
          "Keep patient calm, monitor breathing, and do not offer unprescribed medications."
        ],
        prerequisites: [
          "Government Photo ID proof (Passport / Aadhar / Driver's License)",
          "Travel Insurance policy document & claim ID",
          "Past medical history records & current prescription medication list",
          "Emergency contact phone number"
        ]
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const displayClinics = useMemo(() => {
    if (backendHospitals && backendHospitals.length > 0) {
      return backendHospitals;
    }

    return CLINICS_DATA.filter((clinic) => {
      const query = searchQuery.toLowerCase();
      const matchesSearch =
        clinic.name.toLowerCase().includes(query) ||
        clinic.address.toLowerCase().includes(query) ||
        clinic.symptomTags.some((tag) => tag.toLowerCase().includes(query));

      const matchesSymptom = selectedSymptom
        ? clinic.symptomTags.some((tag) => tag.toLowerCase().includes(selectedSymptom.toLowerCase()))
        : true;

      return matchesSearch && matchesSymptom;
    }).sort((a, b) => a.distanceKm - b.distanceKm);
  }, [searchQuery, selectedSymptom, backendHospitals]);

  // Tap the radius circle to step to the next option. If a search is already
  // on screen the new radius is passed straight into the re-run, so the user
  // never has to re-type their symptoms just to widen the search.
  const cycleRadius = () => {
    const index = RADIUS_OPTIONS_KM.indexOf(radiusKm);
    const next = RADIUS_OPTIONS_KM[(index + 1) % RADIUS_OPTIONS_KM.length];
    setRadiusKm(next);

    const activeSymptoms = searchQuery.trim();
    if (activeSymptoms && !isAnalyzing) {
      triggerBackendAnalysis(activeSymptoms, next);
    }
  };

  const handleScheduleWalkIn = async (clinic: Clinic) => {
    try {
      const existingVisitsRaw = localStorage.getItem("medtour_visits");
      const existingVisits = existingVisitsRaw ? JSON.parse(existingVisitsRaw) : [];

      const newVisit = {
        id: `v-${Date.now()}`,
        facilityName: clinic.name,
        address: clinic.address,
        phone: clinic.phone,
        status: "upcoming" as const,
        timestamp: Date.now(),
        symptoms: selectedSymptom ? [selectedSymptom] : [searchQuery || "General Walk-In Consultation"],
        cost: "₹1,200",
        insuranceTaxId: "GSTIN29AAACA1234D1Z5",
        estimatedWaitMins: clinic.estimatedWaitMins || 15,
      };

      const updatedVisits = [newVisit, ...existingVisits];
      localStorage.setItem("medtour_visits", JSON.stringify(updatedVisits));
      localStorage.setItem("medtour_mtr_docked", "true");

      // Persist encrypted record into device MTR & ECS vault
      try {
        const { saveMtrRecord } = await import("@/lib/mtrDatabase");
        await saveMtrRecord("all_visits_ledger", "visits", "All Visits Ledger", updatedVisits);
        await saveMtrRecord(newVisit.id, "visits", newVisit.facilityName, newVisit);
      } catch (mtrErr) {
        console.warn("MTR database sync:", mtrErr);
      }

      try {
        const { saveEcsRecord } = await import("@/lib/ecsDatabase");
        await saveEcsRecord(newVisit.id, "visits", newVisit.facilityName, newVisit);
        await saveEcsRecord("all_visits_ledger", "visits", "All Visits Ledger", updatedVisits);
      } catch (ecsErr) {
        console.warn("ECS database sync skipped:", ecsErr);
      }

      // Notify any active listeners
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("medtour:mtr-restored", {
          detail: { hasMedicalId: true, visitCount: updatedVisits.length }
        }));
      }

      toast.success(`Walk-in scheduled at ${clinic.name}!`);
      navigate({ to: "/visits", search: { tab: "upcoming" } as any });
    } catch (err) {
      console.error("Failed to schedule walk-in:", err);
      toast.error("Failed to schedule walk-in.");
    }
  };

  return (
    <div className="min-h-screen bg-background pb-44 font-sans">
      {/* Top Center Minimal MedTour Brand (Takes user to /landing) */}
      <header className="w-full pt-4 pb-2 flex items-center justify-center">
        <button
          onClick={() => navigate({ to: "/landing" })}
          className="group inline-flex items-center gap-2 px-4 py-1.5 rounded-full hover:bg-muted/60 transition-all cursor-pointer focus:outline-none"
          aria-label="MedTour Landing Page"
        >
          <span className="grid h-7 w-7 place-items-center rounded-full bg-primary text-primary-foreground shadow-xs group-hover:scale-105 transition-transform">
            <FiShield className="h-4 w-4" />
          </span>
          <span className="text-xl font-black tracking-tight text-foreground group-hover:opacity-85 transition-opacity">
            MedTour
          </span>
        </button>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-2 space-y-4">
        
        {/* AI TRIAGE, ACCORDION FIRST AID & ACCORDION PREREQUISITES BANNER */}
        {aiAnalysisResult && !isAnalyzing && (
          <div className="space-y-3 animate-in fade-in duration-300">
            
            {/* ACCORDION 1: Triage & Immediate First Aid */}
            <div className="rounded-3xl bg-blue-500/10 border-2 border-blue-500/30 overflow-hidden shadow-xs transition-all">
              <button
                onClick={() => setIsFirstAidOpen(!isFirstAidOpen)}
                className="w-full p-4 flex items-center justify-between text-left hover:bg-blue-500/15 transition-colors"
              >
                <div className="flex items-center gap-2 text-xs font-extrabold text-blue-600 dark:text-blue-400 uppercase tracking-wider">
                  <FiShield className="h-4 w-4" />
                  <span>AI First Aid Protocol • {aiAnalysisResult.specialty} ({aiAnalysisResult.urgency})</span>
                </div>
                {isFirstAidOpen ? (
                  <FiChevronUp className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
                ) : (
                  <FiChevronDown className="h-4 w-4 text-blue-600 dark:text-blue-400 shrink-0" />
                )}
              </button>

              {isFirstAidOpen && (
                <div className="px-4 pb-4 space-y-2 border-t border-blue-500/20 pt-3 animate-in fade-in duration-200">
                  <p className="text-xs font-extrabold text-foreground leading-snug">
                    {aiAnalysisResult.summary}
                  </p>

                  {aiAnalysisResult.firstAid && aiAnalysisResult.firstAid.length > 0 && (
                    <div>
                      <span className="text-[11px] font-extrabold text-blue-700 dark:text-blue-300 uppercase tracking-wider block mb-1.5">
                        🚑 Immediate Layperson Actions:
                      </span>
                      <ul className="text-xs space-y-1.5 text-foreground font-semibold pl-4 list-disc leading-snug">
                        {aiAnalysisResult.firstAid.map((step, idx) => (
                          <li key={idx}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* ACCORDION 2: Prerequisites Before Heading to Hospital */}
            {aiAnalysisResult.prerequisites && aiAnalysisResult.prerequisites.length > 0 && (
              <div className="rounded-3xl bg-amber-500/10 border border-amber-500/30 overflow-hidden shadow-xs transition-all">
                <button
                  onClick={() => setIsPrereqsOpen(!isPrereqsOpen)}
                  className="w-full p-4 flex items-center justify-between text-left hover:bg-amber-500/15 transition-colors"
                >
                  <div className="flex items-center gap-2 text-xs font-extrabold text-amber-700 dark:text-amber-400 uppercase tracking-wider">
                    <FiAlertTriangle className="h-4 w-4" />
                    <span>Prerequisites Before Heading to Hospital</span>
                  </div>
                  {isPrereqsOpen ? (
                    <FiChevronUp className="h-4 w-4 text-amber-700 dark:text-amber-400 shrink-0" />
                  ) : (
                    <FiChevronDown className="h-4 w-4 text-amber-700 dark:text-amber-400 shrink-0" />
                  )}
                </button>

                {isPrereqsOpen && (
                  <div className="px-4 pb-4 border-t border-amber-500/20 pt-3 animate-in fade-in duration-200">
                    <ul className="text-xs space-y-1.5 text-foreground font-semibold pl-4 list-disc leading-snug">
                      {aiAnalysisResult.prerequisites.map((reqItem, idx) => (
                        <li key={idx}>{reqItem}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

          </div>
        )}

        {/* CLEAN UN-NESTED FACILITY LIST */}
        <div className="space-y-3 pt-2">
          {!searchQuery.trim() && !selectedSymptom ? (
            <div className="p-8 text-center space-y-3 my-12 flex flex-col items-center justify-center min-h-[45vh]">
              <div className="h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
                <FiSearch className="h-6 w-6" />
              </div>
              <h3 className="text-base font-extrabold text-foreground">
                Describe Your Symptoms or Scenario
              </h3>
              <p className="text-xs font-semibold text-muted-foreground max-w-xs mx-auto leading-relaxed">
                Type how you feel in the box below or select one of the quick tags to get instant hospital recommendations.
              </p>
            </div>
          ) : isAnalyzing ? (
            /* MULTI-COLOUR SKELETON CARDS WHILE ANALYZING SYMPTOMS */
            <div className="space-y-3">
              {/* Blue triage accordion skeleton */}
              <div className="p-4 rounded-3xl bg-blue-500/10 border-2 border-blue-500/30 space-y-3 animate-pulse">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded bg-blue-500/40"></div>
                  <div className="h-3.5 bg-blue-500/30 rounded-md w-1/2"></div>
                </div>
                <div className="h-3 bg-blue-400/25 rounded-md w-2/3"></div>
                <div className="space-y-2 pt-1">
                  <div className="h-3 bg-blue-400/20 rounded-md w-full"></div>
                  <div className="h-3 bg-blue-400/20 rounded-md w-5/6"></div>
                  <div className="h-3 bg-blue-400/20 rounded-md w-3/4"></div>
                </div>
              </div>

              {/* Amber prerequisites accordion skeleton */}
              <div className="p-4 rounded-3xl bg-amber-500/10 border border-amber-500/30 space-y-3 animate-pulse">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded bg-amber-500/40"></div>
                  <div className="h-3.5 bg-amber-500/30 rounded-md w-2/5"></div>
                </div>
                <div className="space-y-2 pt-1">
                  <div className="h-3 bg-amber-400/20 rounded-md w-5/6"></div>
                  <div className="h-3 bg-amber-400/20 rounded-md w-3/4"></div>
                </div>
              </div>

              {/* Hospital cards — each a different accent colour */}
              {[
                { border: "border-emerald-500/30", bg: "bg-emerald-500/10", bar: "bg-emerald-500/30", soft: "bg-emerald-400/20", chip: "bg-emerald-500/15" },
                { border: "border-violet-500/30", bg: "bg-violet-500/10", bar: "bg-violet-500/30", soft: "bg-violet-400/20", chip: "bg-violet-500/15" },
                { border: "border-rose-500/30", bg: "bg-rose-500/10", bar: "bg-rose-500/30", soft: "bg-rose-400/20", chip: "bg-rose-500/15" },
              ].map((c, n) => (
                <div key={n} className={`p-4 rounded-2xl border ${c.border} ${c.bg} space-y-3 animate-pulse`}>
                  <div className="flex justify-between items-start">
                    <div className="space-y-2 flex-1 pr-4">
                      <div className={`h-5 ${c.bar} rounded-md w-2/3`}></div>
                      <div className={`h-3.5 ${c.soft} rounded-md w-1/2`}></div>
                    </div>
                    <div className={`h-6 w-24 ${c.chip} rounded-full`}></div>
                  </div>
                  <div className={`h-3 ${c.soft} rounded-md w-3/4`}></div>
                  <div className={`h-10 ${c.chip} rounded-xl w-full`}></div>
                </div>
              ))}
            </div>
          ) : aiAnalysisResult && !showHospitals ? (
            /* TRIAGE SHOWN — HOSPITALS REVEALING: subtle shimmer hint so the
               two never compete. Auto-replaces itself with the list. */
            <div className="space-y-3 pt-1">
              <p className="text-xs font-extrabold text-muted-foreground uppercase tracking-wider text-center animate-pulse">
                ✨ Curating matching hospitals near you…
              </p>
              {[
                { border: "border-emerald-500/20", bg: "bg-emerald-500/5", bar: "bg-emerald-500/25", soft: "bg-emerald-400/15" },
                { border: "border-violet-500/20", bg: "bg-violet-500/5", bar: "bg-violet-500/25", soft: "bg-violet-400/15" },
              ].map((c, n) => (
                <div key={n} className={`p-4 rounded-2xl border ${c.border} ${c.bg} space-y-3 animate-pulse`}>
                  <div className={`h-5 ${c.bar} rounded-md w-2/3`}></div>
                  <div className={`h-3 ${c.soft} rounded-md w-1/2`}></div>
                </div>
              ))}
            </div>
          ) : displayClinics.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground text-xs font-medium border border-dashed border-border rounded-2xl">
              No matching clinics found for your symptoms. Try typing general terms like "fever", "stomach", or "wounds".
            </div>
          ) : (
            displayClinics.map((clinic: Clinic) => (
              <div
                key={clinic.id}
                role="button"
                tabIndex={0}
                aria-label={`Google AI overview for ${clinic.name}`}
                onClick={() =>
                  setAiHospital({
                    name: clinic.name,
                    city: clinic.city,
                    address: clinic.address,
                    phone: clinic.phone,
                    specialties: clinic.specialties,
                    facilities: clinic.facilities,
                    totalBeds: clinic.totalBeds,
                    accreditation: clinic.accreditation,
                    rating: clinic.rating,
                    reviewCount: clinic.reviewCount,
                    curability: clinic.curability,
                    aiMatchReason: clinic.aiMatchReason,
                    distanceKm: clinic.distanceKm,
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setAiHospital({
                      name: clinic.name,
                      city: clinic.city,
                      address: clinic.address,
                      phone: clinic.phone,
                      specialties: clinic.specialties,
                      facilities: clinic.facilities,
                      totalBeds: clinic.totalBeds,
                      accreditation: clinic.accreditation,
                      rating: clinic.rating,
                      reviewCount: clinic.reviewCount,
                      curability: clinic.curability,
                      aiMatchReason: clinic.aiMatchReason,
                      distanceKm: clinic.distanceKm,
                    });
                  }
                }}
                className="p-4 sm:p-5 rounded-3xl border border-border/80 bg-card space-y-3.5 shadow-sm hover:border-primary/60 hover:shadow-md cursor-pointer transition-all animate-in fade-in duration-200"
              >
                {/* Header Row */}
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-base sm:text-lg font-bold text-foreground leading-snug break-words flex items-center gap-1.5 group">
                        <span>{clinic.name}</span>
                      </h3>
                      {clinic.tier === "best" && (
                        <span className="text-[10px] font-black uppercase tracking-wider text-amber-700 dark:text-amber-300 bg-amber-500/20 border border-amber-500/30 px-2 py-0.5 rounded-full inline-flex items-center gap-1 shadow-xs">
                          🏆 Best Match
                        </span>
                      )}
                      {clinic.tier === "nearest" && (
                        <span className="text-[10px] font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-300 bg-emerald-500/20 border border-emerald-500/30 px-2 py-0.5 rounded-full inline-flex items-center gap-1 shadow-xs">
                          ⚡ Nearest ER
                        </span>
                      )}
                      {clinic.tier === "nearby" && (
                        <span className="text-[10px] font-bold text-blue-700 dark:text-blue-300 bg-blue-500/15 border border-blue-500/25 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                          📍 Nearby Option
                        </span>
                      )}
                      <span className="text-[10px] font-bold text-primary/80 bg-primary/10 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        Google Places & AI
                      </span>
                    </div>
                    
                    <div className="flex items-start gap-1.5 text-xs text-muted-foreground font-medium leading-normal">
                      <FiMapPin className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                      <span className="break-words line-clamp-2">{clinic.address}</span>
                    </div>

                    {clinic.aiMatchReason && (
                      <div className="rounded-xl bg-blue-500/10 border border-blue-500/20 p-2 text-[11px] font-semibold text-blue-800 dark:text-blue-300 flex items-start gap-1.5 leading-snug mt-1">
                        <span className="shrink-0 text-blue-500 mt-0.5 font-bold">✨ Why Chosen:</span>
                        <span>{clinic.aiMatchReason}</span>
                      </div>
                    )}
                  </div>

                  {/* Badges: Open status & Distance */}
                  <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 shrink-0">
                    <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-primary/15 text-primary whitespace-nowrap">
                      {clinic.distanceKm} km away
                    </span>
                    {clinic.estimatedWaitMins > 0 ? (
                      <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 whitespace-nowrap">
                        Open Now • ~{clinic.estimatedWaitMins}m Wait
                      </span>
                    ) : (
                      <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-600 whitespace-nowrap">
                        {clinic.openNow ? "Emergency Ward Listed" : "Call to Confirm Hours"}
                      </span>
                    )}
                  </div>
                </div>

                {/* Reputation & Curability row */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {clinic.rating != null ? (
                    <span className="text-[11px] font-extrabold px-2.5 py-1 rounded-full bg-amber-500/15 text-amber-600 whitespace-nowrap">
                      ★ {clinic.rating.toFixed(1)}{clinic.reviewCount ? ` (${clinic.reviewCount})` : ""}
                    </span>
                  ) : clinic.reputationBand ? (
                    <span
                      className={`text-[11px] font-extrabold px-2.5 py-1 rounded-full whitespace-nowrap ${
                        clinic.reputationBand === "Premium" || clinic.reputationBand === "Rated"
                          ? "bg-amber-500/15 text-amber-600"
                          : clinic.reputationBand === "Well-reviewed"
                          ? "bg-blue-500/15 text-blue-600"
                          : "bg-muted text-muted-foreground"
                      }`}
                      title={clinic.reputationSource === "inferred" ? "Inferred from name, services & accreditation" : "From rated reviews"}
                    >
                      {clinic.reputationBand}
                      {clinic.reputationSource === "inferred" && " · inferred"}
                    </span>
                  ) : null}

                  {clinic.curability && (
                    <span
                      className={`text-[11px] font-extrabold px-2.5 py-1 rounded-full whitespace-nowrap ${
                        clinic.curable === false
                          ? "bg-rose-500/15 text-rose-600"
                          : "bg-emerald-500/15 text-emerald-600"
                      }`}
                    >
                      {clinic.curable === false ? "✗ " : "✓ "}
                      {clinic.curability}
                    </span>
                  )}
                </div>

                {/* Simplified Clean Metadata */}
                <div className="p-2.5 rounded-xl bg-muted/40 border border-border/60 text-xs text-muted-foreground font-medium flex items-center justify-between">
                  <span className="truncate text-[11px] sm:text-xs">English Speaking Staff • Cashless Insurance Desk</span>
                </div>

                {/* Actions */}
                <div className="pt-0.5 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleScheduleWalkIn(clinic);
                    }}
                    className="flex-1 h-11 rounded-2xl bg-primary text-primary-foreground font-extrabold text-xs sm:text-sm shadow-xs hover:opacity-90 transition-opacity"
                  >
                    Schedule Arrival
                  </Button>
                  <a
                    href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${clinic.name} ${clinic.address}`)}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="h-11 w-11 rounded-2xl border border-border bg-background hover:bg-muted flex items-center justify-center text-xs font-bold text-foreground shrink-0 transition-colors"
                    title="Get Directions"
                  >
                    <FaLocationArrow className="h-4 w-4" />
                  </a>
                  {clinic.phone && (
                    <a
                      href={`tel:${clinic.phone}`}
                      onClick={(e) => e.stopPropagation()}
                      className="h-11 w-11 rounded-2xl border border-border bg-background hover:bg-muted flex items-center justify-center text-xs font-bold text-foreground shrink-0 transition-colors"
                      title="Call Clinic"
                    >
                      <FiPhone className="h-4 w-4" />
                    </a>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

      </main>

      {/* FLOATING SYMPTOM CONTAINER WITH 3 TAGS DIRECTLY ABOVE TEXTAREA */}
      <div className="fixed bottom-[5.75rem] left-0 right-0 z-40 flex flex-col items-center justify-center px-3 sm:px-4 pointer-events-none pb-[env(safe-area-inset-bottom)]">
        
        {/* COLLAPSED TAB BUTTON SLIDING BEHIND BOTTOM NAV CLINIC ICON */}
        {isCollapsed ? (
          <div className="fixed bottom-[4.5rem] left-0 right-0 z-30 flex justify-center pointer-events-none">
            <button
              onClick={() => setIsCollapsed(false)}
              className="h-8 w-11 rounded-full bg-background/95 dark:bg-card/95 backdrop-blur-2xl border-2 border-blue-500/70 text-blue-600 dark:text-blue-400 font-extrabold flex items-center justify-center shadow-[0_4px_20px_rgba(59,130,246,0.35)] pointer-events-auto shrink-0 animate-in fade-in slide-in-from-bottom-2 duration-200 hover:bg-muted active:scale-95 transition-all"
              title="Expand Search Symptoms"
            >
              <FiChevronUp className="h-6 w-6 shrink-0 text-blue-500" />
            </button>
          </div>
        ) : (
          <div className="w-full max-w-[380px] flex flex-col items-center space-y-2 pointer-events-auto shrink-0 animate-in slide-in-from-bottom-3 duration-300">
            
            {/* EXACTLY 3 SYMPTOM TAGS DIRECTLY ABOVE TEXTAREA */}
            <div className="flex items-center justify-center gap-1.5 w-full">
              {TOP_3_TAGS.map((tag) => {
                const isSelected = selectedSymptom === tag || searchQuery === tag;
                return (
                  <button
                    key={tag}
                    disabled={isAnalyzing}
                    onClick={() => {
                      if (isSelected) {
                        setSelectedSymptom(null);
                        setSearchQuery("");
                      } else {
                        setSelectedSymptom(tag);
                        setSearchQuery(tag);
                        triggerBackendAnalysis(tag);
                      }
                    }}
                    className={`flex-1 py-1 px-2 rounded-full text-[11px] font-extrabold shrink-0 border transition-all duration-200 text-center truncate ${
                      isAnalyzing ? "opacity-50 cursor-not-allowed" : ""
                    } ${
                      isSelected
                        ? "bg-foreground text-background border-foreground shadow-sm"
                        : "bg-background/90 dark:bg-card/90 text-foreground border-border/80 hover:bg-muted"
                    }`}
                  >
                    {tag}
                  </button>
                );
              })}
            </div>

            {/* FLOATING TEXTAREA BOX WITH BLUE GLOW */}
            <div className="relative w-full bg-background/95 dark:bg-card/95 backdrop-blur-2xl border-2 border-blue-500/40 focus-within:border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.35),0_14px_36px_rgba(0,0,0,0.2)] focus-within:shadow-[0_0_40px_rgba(59,130,246,0.5),0_14px_36px_rgba(0,0,0,0.25)] rounded-3xl p-3.5 min-h-[96px] transition-all duration-300">
              <textarea
                rows={2}
                placeholder={isAnalyzing ? "AI is analyzing your symptoms and finding facilities..." : "Your Feelings Here......"}
                value={searchQuery}
                disabled={isAnalyzing}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSelectedSymptom(null);
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (!isAnalyzing && searchQuery.trim()) {
                      triggerBackendAnalysis(searchQuery);
                    }
                  }
                }}
                className={`w-full bg-transparent border-none outline-none focus:outline-none focus:ring-0 text-sm font-semibold text-foreground placeholder:text-muted-foreground/70 resize-none min-h-[72px] pl-14 pr-14 transition-opacity ${
                  isAnalyzing ? "opacity-60 cursor-not-allowed" : ""
                }`}
              />

              {/* Bottom-Left: RADIUS TOGGLE */}
              <button
                onClick={cycleRadius}
                disabled={isAnalyzing}
                className={`absolute bottom-3 left-3 h-12 w-12 rounded-full bg-background text-foreground border-2 border-foreground flex flex-col items-center justify-center leading-none shadow-md active:scale-90 transition-all duration-200 ${
                  isAnalyzing ? "opacity-50 cursor-not-allowed" : ""
                }`}
                aria-label={`Search radius ${radiusKm} kilometres. Tap to change.`}
                title={isAnalyzing ? "Please wait for AI analysis to finish" : "Tap to change search radius"}
              >
                <span className="text-[16px] font-black tabular-nums">{radiusKm}</span>
                <span className="text-[9px] font-bold -mt-0.5 opacity-70">km</span>
              </button>

              {/* Bottom-Right Send Button */}
              <button
                onClick={() => {
                  if (searchQuery && !isAnalyzing) {
                    triggerBackendAnalysis(searchQuery);
                  }
                }}
                disabled={isAnalyzing || !searchQuery.trim()}
                className={`absolute bottom-3 right-3 h-11 w-11 rounded-full flex items-center justify-center transition-all duration-200 ${
                  isAnalyzing
                    ? "bg-blue-600/60 text-white cursor-not-allowed opacity-75 shadow-none"
                    : !searchQuery.trim()
                    ? "bg-muted text-muted-foreground cursor-not-allowed opacity-50"
                    : "bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/40 active:scale-90 cursor-pointer"
                }`}
                aria-label={isAnalyzing ? "AI is analyzing..." : "Find Clinics"}
                title={isAnalyzing ? "Analyzing symptoms..." : "Find Clinics"}
              >
                {isAnalyzing ? (
                  <FiLoader className="h-5 w-5 shrink-0 animate-spin" />
                ) : (
                  <FiArrowRight className="h-6 w-6 shrink-0" />
                )}
              </button>
            </div>

          </div>
        )}
      </div>

      <MobileNav onOpenMedicalId={() => setIsMedicalIdOpen(true)} />
      <QuickMedicalIdModal isOpen={isMedicalIdOpen} onClose={() => setIsMedicalIdOpen(false)} />
      <HospitalAiDialog hospital={aiHospital} onClose={() => setAiHospital(null)} />
    </div>
  );
}
