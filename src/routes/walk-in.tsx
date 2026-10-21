import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useMemo, useEffect, useRef, useSyncExternalStore } from "react";
import { MobileNav } from "@/components/site/MobileNav.tsx";
import { QuickMedicalIdModal } from "@/components/site/QuickMedicalIdModal";
import { isMtrSignedIn, getPatientName, parseHospitalId } from "@/lib/mtrSession";
import { HospitalAiDialog, type AiHospital } from "@/components/dashboard/HospitalAiDialog";
import { InsuranceTpaBadge, type InsuranceTpaProfile } from "@/components/site/InsuranceTpaBadge";
import { Button } from "@/components/ui/button";
import { FiSearch, FiMapPin, FiPhone, FiArrowRight, FiChevronUp, FiChevronDown, FiShield, FiAlertTriangle, FiLoader, FiMic } from "react-icons/fi";
import { FaLocationArrow } from "react-icons/fa";
import { toast } from "sonner";
import api from "@/lib/api";
import {
  describeGeolocationFailure,
  isPosition,
  readPosition,
} from "@/lib/geolocation";

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
  insuranceTpa?: InsuranceTpaProfile;
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
    cashlessInsurance: false,
    insuranceTpa: {
      cashless_available: false,
      badge_label: "Pay & Claim (Reimbursement)",
      tier: "Private Urgent Clinic",
      accepted_tpas: ["Domestic Claim Receipt"],
      intl_insurers_supported: ["Allianz / Cigna itemized invoice provided"],
      deposit_policy: "Upfront credit card payment. Scan MedTour discharge QR for international claim PDF.",
      instructions: "Pay direct, keep itemized medical invoice, and download the verified claim receipt via MedTour.",
      direct_billing: false,
    },
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
    insuranceTpa: {
      cashless_available: true,
      badge_label: "International Cashless & TPA Desk",
      tier: "NABH / JCI Accredited Tertiary",
      accepted_tpas: ["Medi Assist", "Vidal Health", "Paramount", "FHPL"],
      intl_insurers_supported: ["Allianz Care", "Cigna Global", "Bupa Global", "GeoBlue"],
      deposit_policy: "Direct cashless settlement available with official Guarantee of Payment (GOP).",
      instructions: "Present your Passport and foreign travel insurance policy number at the International Desk.",
      direct_billing: true,
    },
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
    cashlessInsurance: true,
    insuranceTpa: {
      cashless_available: true,
      badge_label: "Apollo TPA Cashless Network",
      tier: "Corporate Outpatient Care",
      accepted_tpas: ["Medi Assist", "Vidal Health", "Apollo Munich/HDFC"],
      intl_insurers_supported: ["Allianz", "Bupa", "Aetna Intl"],
      deposit_policy: "Cashless OPD for covered corporate & international policies with pre-authorization.",
      instructions: "Check in with your digital insurance card at the main billing reception.",
      direct_billing: true,
    },
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

// ---------------------------------------------------------------------------
// Voice dictation (Web Speech API)
//
// Lets a patient SPEAK their issue instead of typing it when they are in no
// shape to type. Chrome/Edge expose it as SpeechRecognition, Safari as
// webkitSpeechRecognition, Firefox not at all -- callers must handle the
// "unsupported" case rather than assume a constructor exists.
// ---------------------------------------------------------------------------
type DictationAlternative = { transcript: string };
type DictationResult = ArrayLike<DictationAlternative> & { isFinal: boolean };
type DictationEvent = { resultIndex: number; results: ArrayLike<DictationResult> };

type DictationEngine = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: DictationEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
};

type DictationCtor = new () => DictationEngine;

function getDictationCtor(): DictationCtor | undefined {
  if (typeof window === "undefined") return undefined;
  const scope = window as unknown as {
    SpeechRecognition?: DictationCtor;
    webkitSpeechRecognition?: DictationCtor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
}

/** Speech follows the language the patient already picked in the app. */
function dictationLanguage(): string {
  try {
    return localStorage.getItem("i18n_language") === "hi" ? "hi-IN" : "en-IN";
  } catch {
    return "en-IN";
  }
}

// Browser capability checks. These are only meaningful in a browser -- the
// server has no window or navigator -- so they are exposed to React through
// useSyncExternalStore (see the component): hydration reuses the server
// snapshot, then React re-renders with the real answer. Reading them during
// the first render instead would make the client's paint differ from the
// server HTML and React would throw the subtree away as a hydration mismatch.
const noopSubscribe = () => () => {};
const serverSaysUnsupported = () => false;

function isSpeechRecognitionSupported(): boolean {
  return Boolean(getDictationCtor());
}

// Firefox has no Web Speech API at all, but it CAN capture audio. Those
// browsers record the utterance and upload it to POST /ai/transcribe, where
// the backend transcribes it with a local Whisper model.
function isRecorderSupported(): boolean {
  if (typeof navigator === "undefined") return false;
  if (!navigator.mediaDevices?.getUserMedia) return false;
  return typeof MediaRecorder !== "undefined";
}

function WalkInDirectoryPage() {
  const navigate = useNavigate();

  // Defaults must match the server's HTML. sessionStorage is restored in an
  // effect just below instead of here: the server has no sessionStorage, so
  // any value read while rendering makes the first client paint differ from
  // the SSR output and React discards the hydrated subtree (hydration
  // mismatch).
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSymptom, setSelectedSymptom] = useState<string | null>(null);
  const [isMedicalIdOpen, setIsMedicalIdOpen] = useState(false);
  // Scheduling is .mtr-gated: no patient accounts exist, so without a docked
  // medical profile there is no identity to book under. Re-read on mount +
  // whenever the profile or vault changes so the buttons un-disable live.
  const [mtrSignedIn, setMtrSignedIn] = useState<boolean>(false);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isFirstAidOpen, setIsFirstAidOpen] = useState(true);
  const [isPrereqsOpen, setIsPrereqsOpen] = useState(true);
  const [aiAnalysisResult, setAiAnalysisResult] = useState<{
    specialty?: string;
    urgency?: string;
    summary?: string;
    firstAid?: string[];
    prerequisites?: string[];
  } | null>(null);
  const [backendHospitals, setBackendHospitals] = useState<Clinic[] | null>(null);
  const [radiusKm, setRadiusKm] = useState<number>(DEFAULT_RADIUS_KM);
  const [showHospitals, setShowHospitals] = useState(false);

  const [userLocation, setUserLocation] = useState<{ lat: number; lng: number }>({
    lat: 19.0760,
    lng: 72.8777,
  });
  const [aiHospital, setAiHospital] = useState<AiHospital | null>(null);

  // Restore the previous visit's state on mount. Effects run in declaration
  // order, so this reads sessionStorage before the persistence effect further
  // down can overwrite it with the defaults above.
  const didRestoreWalkIn = useRef(false);
  useEffect(() => {
    if (didRestoreWalkIn.current) return;
    didRestoreWalkIn.current = true;

    const saved = getInitialWalkInState();
    if (!saved) return;

    if (typeof saved.searchQuery === "string") setSearchQuery(saved.searchQuery);
    if (typeof saved.selectedSymptom === "string") setSelectedSymptom(saved.selectedSymptom);
    if (typeof saved.isCollapsed === "boolean") setIsCollapsed(saved.isCollapsed);
    if (typeof saved.isFirstAidOpen === "boolean") setIsFirstAidOpen(saved.isFirstAidOpen);
    if (typeof saved.isPrereqsOpen === "boolean") setIsPrereqsOpen(saved.isPrereqsOpen);
    if (saved.aiAnalysisResult) setAiAnalysisResult(saved.aiAnalysisResult);
    if (saved.backendHospitals) setBackendHospitals(saved.backendHospitals);
    if (typeof saved.radiusKm === "number") setRadiusKm(saved.radiusKm);
    if (typeof saved.showHospitals === "boolean") setShowHospitals(saved.showHospitals);
    if (saved.userLocation) setUserLocation(saved.userLocation);
  }, []);

  // --- Voice dictation: speak the issue instead of typing it -------------
  //
  // Two engines, picked by what the browser can actually do:
  //   * Web Speech API (Chrome/Edge/Safari) -- transcribes in the browser.
  //   * MediaRecorder -> POST /ai/transcribe (Firefox) -- records here and
  //     transcribes on the server with a local Whisper model.
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const dictationRef = useRef<DictationEngine | null>(null);
  // Finalised words of the current utterance; interim words are recomputed
  // from scratch on every event so nothing is ever counted twice.
  const dictationFinalRef = useRef("");
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recorderChunksRef = useRef<Blob[]>([]);

  // Capability snapshots: false during SSR/hydration (matching the server
  // HTML), the real answer immediately after. See the helpers at module scope.
  const speechSupported = useSyncExternalStore(
    noopSubscribe,
    isSpeechRecognitionSupported,
    serverSaysUnsupported,
  );
  const recorderSupported = useSyncExternalStore(
    noopSubscribe,
    isRecorderSupported,
    serverSaysUnsupported,
  );
  // Neither engine available: the mic cannot do anything, so say so up front.
  const voiceUnavailable = !speechSupported && !recorderSupported;

  const stopMediaTracks = () => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  };

  // Never leave a live microphone behind when the patient navigates away.
  useEffect(() => {
    return () => {
      dictationRef.current?.abort();
      dictationRef.current = null;
      // Detach the recorder FIRST: its onstop would otherwise fire an upload
      // on behalf of a component that no longer exists.
      recorderRef.current = null;
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    };
  }, []);

  // Send the finished recording to the backend and drop the transcript into
  // the symptom box. Does NOT submit the search -- the patient reviews what
  // was heard and presses send, exactly as if they had typed it.
  const transcribeRecording = async (blob: Blob) => {
    const base = searchQuery.trim();
    setIsTranscribing(true);
    try {
      const form = new FormData();
      const ext = blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
      form.append("file", blob, `speech.${ext}`);

      const res = await api.post<{ text: string }>("/ai/transcribe", form, {
        // The axios instance defaults to application/json, which would make
        // axios stringify the FormData instead of uploading it. Declaring
        // multipart here keeps the body intact and lets the browser add the
        // boundary.
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });

      const spoken = res.data?.text?.trim();
      if (!spoken) {
        toast.error("Could not make out any words. Tap the mic and speak again.");
        return;
      }
      setSearchQuery(base ? `${base} ${spoken}` : spoken);
      setSelectedSymptom(null);
      toast.success("Captured your symptoms.");
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      toast.error(
        typeof detail === "string" && detail
          ? detail
          : "Speech-to-text failed. Please type your symptoms instead.",
      );
    } finally {
      setIsTranscribing(false);
    }
  };

  // Firefox path: ask for the microphone (the browser shows its permission
  // prompt here), record until the patient taps the mic again, upload.
  const startRecording = async () => {
    if (!window.isSecureContext) {
      toast.error("The microphone needs a secure page — open this over https:// or localhost.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const name = (err as { name?: string })?.name;
      if (name === "NotAllowedError" || name === "SecurityError") {
        toast.error("Microphone access was blocked. Allow the microphone to speak your symptoms.");
      } else {
        toast.error("Could not open the microphone. Please type your symptoms instead.");
      }
      return;
    }

    let recorder: MediaRecorder;
    try {
      recorder = new MediaRecorder(stream);
    } catch {
      stopMediaTracks();
      toast.error("This browser cannot record audio. Please type your symptoms.");
      return;
    }

    mediaStreamRef.current = stream;
    recorderChunksRef.current = [];

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) recorderChunksRef.current.push(event.data);
    };

    recorder.onstop = () => {
      // Only the recorder we are still tracking may talk to the server.
      if (recorderRef.current !== recorder) return;
      recorderRef.current = null;
      stopMediaTracks();
      const blob = new Blob(recorderChunksRef.current, {
        type: recorder.mimeType || "audio/webm",
      });
      recorderChunksRef.current = [];
      if (blob.size > 0) void transcribeRecording(blob);
    };

    const failRecording = () => {
      recorderRef.current = null;
      stopMediaTracks();
      setIsListening(false);
      toast.error("Recording failed. Please type your symptoms instead.");
    };
    recorder.onerror = failRecording;

    recorderRef.current = recorder;
    setIsListening(true);
    try {
      recorder.start();
    } catch {
      failRecording();
    }
  };

  const toggleVoiceInput = () => {
    if (isListening) {
      if (dictationRef.current) {
        // Web Speech engine stops itself and clears the flag via onend.
        dictationRef.current.stop();
        return;
      }
      // Recorder path: clear the flag now so the box can show its
      // "transcribing" state the moment onstop fires.
      setIsListening(false);
      try {
        recorderRef.current?.stop();
      } catch {
        // Already stopped -- release the mic rather than leave it open.
        recorderRef.current = null;
        stopMediaTracks();
      }
      return;
    }
    if (isAnalyzing || isTranscribing) return;

    if (!speechSupported) {
      // No Web Speech API here (Firefox): record and let the server listen.
      void startRecording();
      return;
    }

    const DictationCtor = getDictationCtor();
    if (!DictationCtor) {
      toast.error("Voice input could not start here. Please type your symptoms instead.");
      return;
    }

    const engine = new DictationCtor();
    engine.lang = dictationLanguage();
    // One breath at a time: the engine stops itself when the patient pauses,
    // and tapping the mic again simply carries on from the current text.
    engine.continuous = false;
    engine.interimResults = true;
    engine.maxAlternatives = 1;

    const base = searchQuery.trim();
    dictationFinalRef.current = "";

    engine.onresult = (event) => {
      let finalPart = "";
      let interimPart = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const text = result[0]?.transcript ?? "";
        if (result.isFinal) finalPart += text;
        else interimPart += text;
      }
      if (finalPart) dictationFinalRef.current += finalPart;
      const spoken = `${dictationFinalRef.current}${interimPart}`.replace(/\s+/g, " ").trim();
      setSearchQuery(base ? `${base} ${spoken}` : spoken);
      setSelectedSymptom(null);
    };

    engine.onerror = (event) => {
      dictationRef.current = null;
      setIsListening(false);
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        toast.error("Microphone access was blocked. Allow the microphone to speak your symptoms.");
      } else if (event.error !== "aborted" && event.error !== "no-speech") {
        toast.error("Could not hear that. Please try speaking again.");
      }
    };

    engine.onend = () => {
      dictationRef.current = null;
      setIsListening(false);
    };

    dictationRef.current = engine;
    setIsListening(true);
    try {
      engine.start();
    } catch {
      // start() throws when a previous session is still winding down.
      dictationRef.current = null;
      setIsListening(false);
    }
  };

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

  // Watch GPS position. Same two-stage read as the Landing page (see
  // lib/geolocation): Android answers the cheap cache/Wi-Fi fix first and
  // only then spends a longer budget waiting on satellites -- the old single
  // request here allowed 5 seconds, after which the search below would
  // silently fire with the default coordinates. A failure is worth one toast
  // so wrong-city results never look like correct ones.
  useEffect(() => {
    if (!navigator.geolocation) return;
    let cancelled = false;

    void (async () => {
      const outcome = await readPosition();
      if (cancelled) return;

      if (!isPosition(outcome)) {
        console.warn("[geolocation] unavailable:", outcome?.code, outcome?.message);
        toast.error(
          describeGeolocationFailure(
            outcome,
            "Nearby results will use the default position.",
          ) ?? "Couldn't get your location.",
        );
        return;
      }

      // Browsers have handed back an empty position before (non-secure
      // origins), and an unguarded read threw. When no fix arrives the
      // search simply falls back to the default coordinates below.
      const lat = outcome?.coords?.latitude;
      const lng = outcome?.coords?.longitude;
      if (
        typeof lat === "number" &&
        typeof lng === "number" &&
        !Number.isNaN(lat) &&
        !Number.isNaN(lng)
      ) {
        setUserLocation({ lat, lng });
      } else {
        console.warn("[geolocation] unusable position payload:", outcome);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  // Two-step reveal: once triage is shown, fade the hospital list in after a
  // short beat so the user reads triage first. Kept brief so the AI search
  // never feels slower than it is. Fires on the triage result alone (the
  // offline fallback has triage but no backend hospitals, and must
  // reveal the static list rather than spin forever).
  useEffect(() => {
    if (!aiAnalysisResult) {
      setShowHospitals(false);
      return;
    }
    const t = setTimeout(() => setShowHospitals(true), 400);
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

  // Track .mtr sign-in so "Schedule Arrival" is enabled/disabled live. The
  // modal and vault restore both re-dispatch this event when the profile
  // changes, and it re-reads the flag on mount.
  useEffect(() => {
    const refresh = () => setMtrSignedIn(isMtrSignedIn());
    refresh();
    window.addEventListener("medtour:mtr-restored", refresh);
    window.addEventListener("storage", refresh);
    window.addEventListener("focus", refresh);
    return () => {
      window.removeEventListener("medtour:mtr-restored", refresh);
      window.removeEventListener("storage", refresh);
      window.removeEventListener("focus", refresh);
    };
  }, []);

  const triggerBackendAnalysis = async (symptomsText: string, radiusOverride?: number) => {
    if (!symptomsText.trim() || isAnalyzing) return;
    setIsAnalyzing(true);
    setShowHospitals(false);

    const lat = typeof userLocation?.lat === "number" && !isNaN(userLocation.lat) ? userLocation.lat : 19.0760;
    const lng = typeof userLocation?.lng === "number" && !isNaN(userLocation.lng) ? userLocation.lng : 72.8777;

    // Step 1: Immediate First Aid Triage (< 1.5 seconds)
    // Dispatches Red Cross / NIM first-aid directly so the patient sees actionable instructions right away.
    try {
      api.post("/ai/triage-firstaid", { symptoms: symptomsText }).then((triageRes) => {
        if (triageRes.data) {
          setAiAnalysisResult((prev) => ({
            specialty: triageRes.data.specialty,
            urgency: triageRes.data.urgency,
            summary: triageRes.data.summary,
            firstAid: triageRes.data.firstAid,
            prerequisites: triageRes.data.prerequisites,
          }));
        }
      }).catch((triageErr) => {
        console.warn("Fast triage endpoint warning:", triageErr);
      });
    } catch (e) {
      console.warn("Immediate triage dispatch error:", e);
    }

    // Step 2: Full Hospital Discovery & Recommendation Workflow
    try {
      const res = await api.post(
        "/ai/analyze",
        {
          symptoms: symptomsText,
          latitude: lat,
          longitude: lng,
          radius_km: radiusOverride ?? radiusKm,
        },
        { timeout: 50000 }
      );

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
            reputationBand: h.reputation_band,
            reputationSource: h.reputation_source,
            rating: h.rating ?? null,
            reviewCount: h.review_count ?? null,
            curable: h.curable,
            curability: h.curability,
            insuranceTpa: h.insurance_tpa,
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
      // Offline emergency advice fallback only if fast triage hasn't set it yet
      setAiAnalysisResult((existing) => existing || {
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

  // Tap the radius circle to step to the next option.
  //
  // The radius filter is applied SERVER side, so results that are already on
  // screen only stay honest if the new radius is fed straight back into a
  // re-run -- otherwise the badge would read "25 km" over a list fetched at
  // 10 km. That re-run is therefore only armed once there are real server
  // results to refresh; while the user is still composing their symptoms,
  // tapping the radius merely stores the value for the next send.
  const cycleRadius = () => {
    const index = RADIUS_OPTIONS_KM.indexOf(radiusKm);
    const next = RADIUS_OPTIONS_KM[(index + 1) % RADIUS_OPTIONS_KM.length];
    setRadiusKm(next);

    const activeSymptoms = searchQuery.trim();
    const hasServerResults = Boolean(backendHospitals?.length);
    if (activeSymptoms && hasServerResults && !isAnalyzing) {
      triggerBackendAnalysis(activeSymptoms, next);
    }
  };

  const handleScheduleWalkIn = async (clinic: Clinic) => {
    // No patient accounts — the docked .mtr profile IS the identity. Without
    // it there is no name/reason to send, so scheduling is refused outright.
    const patientName = getPatientName();
    if (!isMtrSignedIn() || !patientName) {
      toast.error(
        "Sign in with your .mtr file to schedule an appointment. Dock your medical profile first.",
        { description: "Open Medical ID from the nav and import or create your .mtr profile." },
      );
      setIsMedicalIdOpen(true);
      return;
    }

    const hospitalId = parseHospitalId(clinic.id);
    if (hospitalId === null) {
      toast.error("This clinic has no bookable facility id. Try another hospital.");
      return;
    }

    const reason =
      (selectedSymptom || searchQuery || "General Walk-In Consultation").trim();

    const scheduledFor = new Date();
    scheduledFor.setDate(scheduledFor.getDate() + 1);

    let created: any = null;
    try {
      // Client/server booking: the server mints the unique appointment id
      // that the test doctor's portal and the QR flow both key on.
      const res = await api.post("/appointments", {
        hospital_id: hospitalId,
        patient_name: patientName,
        reason,
        department: selectedSymptom || aiAnalysisResult?.specialty || "General Medicine",
        appointment_time: scheduledFor.toISOString(),
      });
      created = res.data;
    } catch (err: any) {
      console.error("Failed to schedule walk-in:", err);
      toast.error(
        err?.response?.data?.detail ||
          "Could not schedule this appointment. Is the backend running?",
      );
      return;
    }

    try {
      const existingVisitsRaw = localStorage.getItem("medtour_visits");
      const existingVisits = existingVisitsRaw ? JSON.parse(existingVisitsRaw) : [];

      const newVisit = {
        // Keyed on the server-assigned id so the row survives a reload and
        // can be matched against the doctor's QR payload later.
        id: `appt-${created.id}`,
        facilityName: clinic.name,
        address: clinic.address,
        phone: clinic.phone,
        status: "upcoming" as const,
        timestamp: scheduledFor.getTime(),
        symptoms: [reason],
        cost: "₹1,200",
        insuranceTaxId: "GSTIN29AAACA1234D1Z5",
        estimatedWaitMins: clinic.estimatedWaitMins || 15,
        appointmentCode: created.appointment_code,
        department: created.department,
        patientName,
      };

      const updatedVisits = [
        newVisit,
        ...existingVisits.filter((v: any) => v.id !== newVisit.id),
      ];
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

      toast.success(
        `Appointment scheduled at ${clinic.name} — ID ${created.appointment_code}`,
        { description: "Your doctor will see it on their portal." },
      );
      navigate({ to: "/visits", search: { tab: "upcoming" } as any });
    } catch (err) {
      console.error("Failed to schedule walk-in:", err);
      toast.error("Appointment was booked but could not be saved locally.");
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
          <span className="text-xl font-black tracking-tight text-foreground group-hover:opacity-85 transition-opacity">
            MedTour
          </span>
        </button>
      </header>

      <main className="max-w-3xl lg:max-w-7xl xl:max-w-[90rem] mx-auto px-4 py-2 space-y-4">
        
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
        <div className="space-y-3 pt-2 lg:grid lg:grid-cols-2 lg:gap-4 lg:items-start lg:space-y-0">
          {!searchQuery.trim() && !selectedSymptom ? (
            <div className="p-8 sm:p-10 text-center space-y-5 flex flex-col items-center justify-center min-h-[45vh] lg:min-h-[58vh] lg:col-span-2">
              <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
                <FiSearch className="h-7 w-7" />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl font-extrabold text-foreground">
                  Describe Your Symptoms or Scenario
                </h3>
                <p className="text-sm font-semibold text-muted-foreground max-w-md mx-auto leading-relaxed">
                  Type how you feel in the box below or pick one of the quick
                  tags to get instant hospital recommendations.
                </p>
              </div>

              {/* Fills the desktop void with something actionable instead of
                  leaving a blank column above the floating search bar. */}
              <div className="grid w-full max-w-3xl grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
                {[
                  {
                    icon: "🩺",
                    title: "Symptom search",
                    desc: "e.g. “high fever for 2 days”",
                  },
                  {
                    icon: "🏨",
                    title: "Browse by specialty",
                    desc: "Cardiology, Ortho, ENT…",
                  },
                  {
                    icon: "📍",
                    title: "Nearest to you",
                    desc: "Uses your GPS position",
                  },
                ].map((c) => (
                  <div
                    key={c.title}
                    className="rounded-2xl border border-border/70 bg-card p-4 text-left space-y-1"
                  >
                    <div className="text-lg">{c.icon}</div>
                    <p className="text-xs font-extrabold text-foreground">
                      {c.title}
                    </p>
                    <p className="text-[11px] font-semibold text-muted-foreground">
                      {c.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : isAnalyzing ? (
            /* MULTI-COLOUR SKELETON CARDS WHILE ANALYZING SYMPTOMS */
            <div className="space-y-3 lg:col-span-2">
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
            <div className="space-y-3 pt-1 lg:col-span-2">
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
            <div className="p-8 text-center text-muted-foreground text-xs font-medium border border-dashed border-border rounded-2xl lg:col-span-2">
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

                {/* Insurance & TPA Network Information */}
                <InsuranceTpaBadge 
                  profile={clinic.insuranceTpa} 
                  hospitalName={clinic.name} 
                />

                {/* Actions */}
                <div className="pt-0.5 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                  <Button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!mtrSignedIn) {
                        toast.error(
                          "Sign in with your .mtr file to schedule an appointment.",
                          { description: "Dock your medical profile from Medical ID first." },
                        );
                        setIsMedicalIdOpen(true);
                        return;
                      }
                      handleScheduleWalkIn(clinic);
                    }}
                    disabled={!mtrSignedIn}
                    title={
                      mtrSignedIn
                        ? "Schedule this arrival"
                        : "Sign in with your .mtr file to schedule an appointment"
                    }
                    className="flex-1 h-11 rounded-2xl bg-primary text-primary-foreground font-extrabold text-xs sm:text-sm shadow-xs hover:opacity-90 transition-opacity disabled:opacity-45 disabled:cursor-not-allowed"
                  >
                    {mtrSignedIn ? "Schedule Arrival" : "Sign in to Schedule"}
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
            <div className={`relative w-full bg-background/95 dark:bg-card/95 backdrop-blur-2xl border-2 border-blue-500/40 focus-within:border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.35),0_14px_36px_rgba(0,0,0,0.2)] focus-within:shadow-[0_0_40px_rgba(59,130,246,0.5),0_14px_36px_rgba(0,0,0,0.25)] rounded-3xl p-3.5 min-h-[96px] transition-all duration-300 ${isListening ? "border-rose-500/70 shadow-[0_0_30px_rgba(244,63,94,0.4),0_14px_36px_rgba(0,0,0,0.2)]" : ""}`}>
              <textarea
                rows={2}
                placeholder={
                  isTranscribing
                    ? "Turning your voice into text..."
                    : isListening
                    ? "Listening... speak your symptoms now"
                    : isAnalyzing
                    ? "AI is analyzing your symptoms and finding facilities..."
                    : "Your Feelings Here......"
                }
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
                className={`w-full bg-transparent border-none outline-none focus:outline-none focus:ring-0 text-sm font-semibold text-foreground placeholder:text-muted-foreground/70 resize-none min-h-[72px] pl-14 pr-[7.5rem] transition-opacity ${
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

              {/* VOICE DICTATION BUTTON: speak the issue instead of typing.
                  Chromium/Safari dictate in the browser; Firefox records and
                  the server transcribes it (POST /ai/transcribe). */}
              <button
                onClick={toggleVoiceInput}
                disabled={isAnalyzing || isTranscribing}
                className={`absolute bottom-3 right-[4.25rem] h-11 w-11 rounded-full flex items-center justify-center transition-all duration-200 ${
                  isTranscribing
                    ? "bg-blue-600 text-white shadow-lg shadow-blue-500/40 cursor-wait"
                    : isListening
                    ? "bg-rose-600 text-white shadow-lg shadow-rose-500/50 animate-pulse active:scale-90"
                    : isAnalyzing
                    ? "bg-muted text-muted-foreground cursor-not-allowed opacity-50"
                    : voiceUnavailable
                    ? "bg-muted text-muted-foreground/70 border-2 border-border/70 opacity-60"
                    : "bg-background dark:bg-card text-foreground border-2 border-foreground/70 hover:bg-muted shadow-md active:scale-90"
                }`}
                aria-label={
                  isTranscribing
                    ? "Transcribing your recording"
                    : isListening
                    ? "Stop listening"
                    : voiceUnavailable
                    ? "Voice input is unavailable in this browser"
                    : speechSupported
                    ? "Speak your symptoms instead of typing"
                    : "Record your symptoms to have them transcribed"
                }
                title={
                  isTranscribing
                    ? "Transcribing..."
                    : isListening
                    ? "Tap to stop listening"
                    : voiceUnavailable
                    ? "Voice input is unavailable in this browser"
                    : speechSupported
                    ? "Speak your symptoms"
                    : "Record your voice — it is transcribed on the server"
                }
              >
                {isTranscribing ? (
                  <FiLoader className="h-5 w-5 shrink-0 animate-spin" />
                ) : (
                  <FiMic className="h-5 w-5 shrink-0" />
                )}
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

            {/* Neither engine can turn speech into text here, so say so up
                front rather than letting a tap look like a dead button. */}
            {voiceUnavailable && (
              <p className="w-full text-center text-[10px] font-bold leading-tight text-muted-foreground/80 px-1">
                🎤 Voice input isn't available in this browser — please type your symptoms.
              </p>
            )}

          </div>
        )}
      </div>

      <MobileNav onOpenMedicalId={() => setIsMedicalIdOpen(true)} />
      <QuickMedicalIdModal isOpen={isMedicalIdOpen} onClose={() => setIsMedicalIdOpen(false)} />
      <HospitalAiDialog hospital={aiHospital} onClose={() => setAiHospital(null)} />
    </div>
  );
}
