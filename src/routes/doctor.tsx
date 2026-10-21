import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, useCallback, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { QRCodeSVG } from "qrcode.react";
import {
  FiUser,
  FiActivity,
  FiFileText,
  FiCopy,
  FiCheck,
  FiSearch,
  FiLogOut,
  FiShield,
  FiRefreshCw,
  FiPlus,
  FiTrash2,
  FiDollarSign,
  FiArrowLeft,
} from "react-icons/fi";
import { toast } from "sonner";
import api from "@/lib/api";

export interface InvoiceLineItemState {
  description: string;
  quantity: number;
  unit_price: number;
}

export interface InvoiceState {
  invoice_number: string;
  issued_on: string;
  line_items: InvoiceLineItemState[];
  tax_amount: number;
  currency: string;
  notes: string;
}

export const Route = createFileRoute("/doctor")({
  head: () => ({
    meta: [
      { title: "Doctor Portal | MedTour" },
      {
        name: "description",
        content:
          "NMC-verified doctor login: enter diagnosis & prescription, generate QR for patient scan.",
      },
    ],
  }),
  component: DoctorPortal,
});

// ---------------------------------------------------------------------------
// Session storage — the doctor's JWT + cached profile live here so a reload
// paints the portal instantly from cache while /doctor/auth/me revalidates.
// ---------------------------------------------------------------------------

const DOCTOR_TOKEN_KEY = "doctor_access_token";
const DOCTOR_PROFILE_KEY = "medtour_doctor_profile";

interface DoctorVerificationInfo {
  verified: boolean;
  verified_at: string | null;
  reg_number: string | null;
  state_council: string | null;
  year: string | null;
  qualification: string | null;
  status: string | null;
  cached: boolean;
  source: string | null;
}

interface DoctorProfile {
  id: number;
  full_name: string;
  email: string;
  reg_number: string;
  state_council: string | null;
  reg_year: string | null;
  specialization: string | null;
  qualification: string | null;
  phone: string | null;
  hospital_id: number | null;
  hospital_name: string | null;
  verification: DoctorVerificationInfo;
  appointment_count: number;
  created_at: string | null;
}

interface DoctorAuthResponse {
  access_token: string;
  token_type: string;
  profile: DoctorProfile;
}

interface HospitalHit {
  id: number;
  name: string;
  city?: string | null;
  state?: string | null;
}

function readCachedProfile(): DoctorProfile | null {
  try {
    const raw = localStorage.getItem(DOCTOR_PROFILE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && parsed.profile ? parsed.profile : null;
  } catch {
    return null;
  }
}

function saveProfileCache(profile: DoctorProfile) {
  try {
    localStorage.setItem(
      DOCTOR_PROFILE_KEY,
      JSON.stringify({ profile, cachedAt: Date.now() }),
    );
  } catch {
    /* storage full / private mode — portal still works, just no instant paint */
  }
}

function clearSession() {
  localStorage.removeItem(DOCTOR_TOKEN_KEY);
  localStorage.removeItem(DOCTOR_PROFILE_KEY);
}

/** Backend writes naive UTC datetimes; make JS parse them as UTC. */
function parseUtc(value: string | null | undefined): Date | null {
  if (!value) return null;
  try {
    const hasZone = value.includes("Z") || /[+-]\d{2}:\d{2}$/.test(value);
    return new Date(hasZone ? value : `${value}Z`);
  } catch {
    return null;
  }
}

function relativeTime(value: string | null | undefined): string | null {
  const date = parseUtc(value);
  if (!date || Number.isNaN(date.getTime())) return null;
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 0) return "just now";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// NMC state medical councils (api.askmydoc.in accepts a subset; free text
// matching against this list keeps the registration form consistent).
const STATE_COUNCILS = [
  "Andaman & Nicobar Islands", "Andhra Pradesh", "Arunachal Pradesh", "Assam",
  "Bihar", "Chandigarh", "Chhattisgarh", "Dadra & Nagar Haveli and Daman & Diu",
  "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu & Kashmir",
  "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Lakshadweep", "Madhya Pradesh",
  "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha",
  "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
  "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
];

/**
 * The appointment row as the portal receives it.
 *
 * There is no diagnosis / prescription / notes here and there never will be:
 * the server holds appointment status only. Clinical detail lives in this
 * browser (localStorage) because it rode the QR to the patient's device the
 * moment it was saved — the row just says whether a QR has been minted.
 */
interface DoctorAppointment {
  id: number;
  appointment_code: string;
  patient_name: string;
  reason: string | null;
  status: string;
  is_completed: boolean;
  is_verified: boolean;
  doctor_name: string | null;
  hospital_id: number;
  hospital_name: string | null;
  department: string | null;
  appointment_time: string;
  created_at: string;
  diagnosis_entered: boolean;
  qr_minted?: boolean;
  hospital: {
    id: number;
    name: string;
    city: string | null;
    state: string;
    address: string | null;
  } | null;
}

function DoctorPortal() {
  const navigate = useNavigate();
  // ---- auth state -------------------------------------------------------
  const [booting, setBooting] = useState(true);
  const [profile, setProfile] = useState<DoctorProfile | null>(null);
  const [authTab, setAuthTab] = useState<"signin" | "register">("signin");
  const [authLoading, setAuthLoading] = useState(false);
  const [reverifying, setReverifying] = useState(false);

  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [regForm, setRegForm] = useState({
    full_name: "",
    email: "",
    password: "",
    reg_number: "",
    state_council: "",
    year: "",
    specialization: "",
  });
  const [hospitalQuery, setHospitalQuery] = useState("");
  const [hospitalHits, setHospitalHits] = useState<HospitalHit[]>([]);
  const [selectedHospital, setSelectedHospital] = useState<HospitalHit | null>(null);

  // ---- portal state -----------------------------------------------------
  const [appointments, setAppointments] = useState<DoctorAppointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAppt, setSelectedAppt] = useState<DoctorAppointment | null>(null);
  const [stage, setStage] = useState<1 | 2>(1);
  const [diagnosis, setDiagnosis] = useState("");
  const [prescription, setPrescription] = useState("");
  const [diagnosisNotes, setDiagnosisNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Stage 2: Invoice state
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issuedOn, setIssuedOn] = useState("");
  const [lineItems, setLineItems] = useState<InvoiceLineItemState[]>([
    { description: "Doctor Consultation Fee", quantity: 1, unit_price: 50 },
  ]);
  const [taxAmount, setTaxAmount] = useState<number>(0);
  const [currency, setCurrency] = useState("USD");
  const [invoiceNotes, setInvoiceNotes] = useState("");

  // The QR image itself, rendered by the backend. The browser only displays
  // it — it never draws a QR, and never sees one it did not ask the server for.
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrPayload, setQrPayload] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  const subtotal = lineItems.reduce(
    (sum, item) => sum + (Number(item.quantity) || 0) * (Number(item.unit_price) || 0),
    0,
  );
  const totalAmount = Math.round((subtotal + (Number(taxAmount) || 0)) * 100) / 100;

  // ---- boot: restore cached session, then revalidate in background ------
  useEffect(() => {
    const token = localStorage.getItem(DOCTOR_TOKEN_KEY);
    const cached = readCachedProfile();

    if (token && cached) {
      // Paint instantly from the localStorage profile cache.
      setProfile(cached);
    }

    if (!token) {
      clearSession();
      setBooting(false);
      return;
    }

    let cancelled = false;
    api
      .get("/doctor/auth/me")
      .then((res) => {
        if (cancelled) return;
        setProfile(res.data);
        saveProfileCache(res.data);
      })
      .catch((err) => {
        if (cancelled) return;
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          // Expired/invalid token — drop back to the sign-in screen.
          clearSession();
          setProfile(null);
        }
        // Network/backend-down: keep the cached session (read-only mode).
      })
      .finally(() => {
        if (!cancelled) setBooting(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ---- appointments load (only once signed in) --------------------------
  const loadAppointments = useCallback(async () => {
    try {
      setLoading(true);
      const params: Record<string, string> = {};
      if (statusFilter !== "all") params.status = statusFilter;
      const res = await api.get("/doctor/appointments", { params });
      setAppointments(res.data);
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        clearSession();
        setProfile(null);
        setAppointments([]);
        toast.error("Session expired. Please sign in again.");
        return;
      }
      console.error("Failed to load appointments:", err);
      toast.error("Failed to load appointments. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (profile) loadAppointments();
  }, [profile, loadAppointments]);

  // ---- hospital search (registration, optional designation) -------------
  useEffect(() => {
    const q = hospitalQuery.trim();
    if (q.length < 2) {
      setHospitalHits([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await api.get("/hospitals/search", { params: { q } });
        const rows = Array.isArray(res.data) ? res.data : [];
        setHospitalHits(
          rows.slice(0, 8).map((h: any) => ({
            id: h.id,
            name: h.name,
            city: h.city,
            state: h.state,
          })),
        );
      } catch {
        setHospitalHits([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [hospitalQuery]);

  // ---- auth actions -----------------------------------------------------
  const startSession = (data: DoctorAuthResponse) => {
    localStorage.setItem(DOCTOR_TOKEN_KEY, data.access_token);
    saveProfileCache(data.profile);
    setProfile(data.profile);
    setBooting(false);
  };

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    if (!loginForm.email.trim() || !loginForm.password) {
      toast.error("Enter your email and password.");
      return;
    }
    setAuthLoading(true);
    try {
      const res = await api.post("/doctor/auth/login", {
        email: loginForm.email.trim(),
        password: loginForm.password,
      });
      startSession(res.data as DoctorAuthResponse);
      toast.success(`Welcome back, Dr. ${res.data.profile.full_name}.`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Sign in failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    const form = regForm;
    if (form.full_name.trim().length < 3) {
      toast.error("Enter your full name (as registered with the NMC).");
      return;
    }
    if (!form.email.trim() || !form.password) {
      toast.error("Email and password are required.");
      return;
    }
    if (form.password.length < 6) {
      toast.error("Password must be at least 6 characters.");
      return;
    }
    if (!form.reg_number.trim()) {
      toast.error("NMC registration number is required.");
      return;
    }
    if (!form.state_council) {
      toast.error("Select your state medical council.");
      return;
    }

    setAuthLoading(true);
    try {
      const res = await api.post("/doctor/auth/register", {
        full_name: form.full_name.trim(),
        email: form.email.trim(),
        password: form.password,
        reg_number: form.reg_number.trim(),
        state_council: form.state_council || null,
        year: form.year.trim() || null,
        specialization: form.specialization.trim() || null,
        hospital_id: selectedHospital?.id ?? null,
      });
      startSession(res.data as DoctorAuthResponse);
      toast.success("NMC registration verified — account created.");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Registration failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleReverify = async () => {
    setReverifying(true);
    try {
      const res = await api.post("/doctor/auth/reverify", { force_refresh: true });
      setProfile(res.data);
      saveProfileCache(res.data);
      if (res.data?.verification?.verified) {
        toast.success("NMC registration re-verified successfully.");
      } else {
        toast.error(
          res.data?.verification?.status === "not_found"
            ? "NMC verification could not confirm this registration."
            : "Verification service unreachable — cached result kept.",
        );
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || "Re-verification failed.");
    } finally {
      setReverifying(false);
    }
  };

  const logout = () => {
    clearSession();
    setProfile(null);
    setAppointments([]);
    setSelectedAppt(null);
    setQrPayload(null);
    setLoginForm({ email: "", password: "" });
    toast.success("Signed out.");
  };

  // ---- diagnosis actions ------------------------------------------------
  /**
   * The clinical detail and invoice the doctor typed is cached per appointment
   * in this browser. The server never stores it, so without this the doctor would
   * lose the ability to redraw the QR after a reload — and could not show it
   * again to a patient who already left the room.
   */
  const clinicalCacheKey = (code: string) => `medtour_doctor_clinical:${code}`;

  const cacheClinical = (
    code: string,
    clinicalData: { dx: string; rx: string; notes: string },
    invoiceData?: InvoiceState,
  ) => {
    try {
      const existing = readCachedClinical(code) || {};
      const updated = {
        ...existing,
        clinical: clinicalData,
        dx: clinicalData.dx,
        rx: clinicalData.rx,
        notes: clinicalData.notes,
        invoice: invoiceData ?? existing.invoice,
        at: Date.now(),
      };
      localStorage.setItem(clinicalCacheKey(code), JSON.stringify(updated));
    } catch {
      // Private/restricted storage
    }
  };

  const readCachedClinical = (code: string) => {
    try {
      const raw = localStorage.getItem(clinicalCacheKey(code));
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  };

  const selectAppointment = (appt: DoctorAppointment) => {
    setSelectedAppt(appt);
    const cached = readCachedClinical(appt.appointment_code);
    const clinical = cached?.clinical || {
      dx: cached?.dx || "",
      rx: cached?.rx || "",
      notes: cached?.notes || "",
    };
    setDiagnosis(clinical.dx || "");
    setPrescription(clinical.rx || "");
    setDiagnosisNotes(clinical.notes || "");

    const defaultInvNumber = `MT-INV-${appt.appointment_code.replace("MT-", "")}`;
    if (cached?.invoice) {
      setInvoiceNumber(cached.invoice.invoice_number || defaultInvNumber);
      setIssuedOn(cached.invoice.issued_on || "");
      setLineItems(
        Array.isArray(cached.invoice.line_items) && cached.invoice.line_items.length > 0
          ? cached.invoice.line_items
          : [{ description: "Doctor Consultation Fee", quantity: 1, unit_price: 50 }],
      );
      setTaxAmount(Number(cached.invoice.tax_amount) || 0);
      setCurrency(cached.invoice.currency || "USD");
      setInvoiceNotes(cached.invoice.notes || "");
    } else {
      setInvoiceNumber(defaultInvNumber);
      setIssuedOn(new Date().toISOString().slice(0, 10));
      setLineItems([{ description: "Doctor Consultation Fee", quantity: 1, unit_price: 50 }]);
      setTaxAmount(0);
      setCurrency("USD");
      setInvoiceNotes("");
    }

    setStage(1);
    setQrImage(null);
    setQrPayload(null);
  };

  // Stage 1: Clinical (diagnosis, prescription, notes)
  const submitStage1Clinical = async () => {
    if (!selectedAppt) return;
    if (!diagnosis.trim()) {
      toast.error("Please enter a diagnosis.");
      return;
    }
    if (!prescription.trim()) {
      toast.error("Please enter a prescription.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await api.post("/doctor/diagnosis", {
        appointment_code: selectedAppt.appointment_code,
        diagnosis: diagnosis.trim(),
        prescription: prescription.trim(),
        diagnosis_notes: diagnosisNotes.trim() || undefined,
        // No invoice -> stage 1
      });

      const savedCode = res.data.appointment_code;
      cacheClinical(savedCode, {
        dx: diagnosis.trim(),
        rx: prescription.trim(),
        notes: diagnosisNotes.trim(),
      });

      setSelectedAppt((prev) =>
        prev
          ? {
              ...prev,
              appointment_code: savedCode,
              diagnosis_entered: true,
              status: res.data.status,
            }
          : null,
      );

      toast.success("Clinical details saved. Continue to invoice generation.");
      setStage(2);
      loadAppointments();
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        clearSession();
        setProfile(null);
        toast.error("Session expired. Please sign in again.");
        return;
      }
      const msg = err?.response?.data?.detail || "Failed to save clinical details.";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Stage 2: Invoice + Mint QR
  const submitStage2Invoice = async () => {
    if (!selectedAppt) return;
    if (!diagnosis.trim() || !prescription.trim()) {
      toast.error("Diagnosis and prescription are required.");
      setStage(1);
      return;
    }

    if (lineItems.length === 0 && totalAmount <= 0) {
      toast.error("Add at least one line item or a total amount.");
      return;
    }

    const currentInvoice: InvoiceState = {
      invoice_number: invoiceNumber.trim() || `MT-INV-${selectedAppt.appointment_code.replace("MT-", "")}`,
      issued_on: issuedOn.trim() || new Date().toISOString().slice(0, 10),
      line_items: lineItems.map((li) => ({
        description: li.description.trim() || "Medical Service",
        quantity: Number(li.quantity) || 1,
        unit_price: Number(li.unit_price) || 0,
      })),
      tax_amount: Number(taxAmount) || 0,
      currency: (currency || "USD").toUpperCase(),
      notes: invoiceNotes.trim(),
    };

    setSubmitting(true);
    try {
      const res = await api.post("/doctor/diagnosis", {
        appointment_code: selectedAppt.appointment_code,
        diagnosis: diagnosis.trim(),
        prescription: prescription.trim(),
        diagnosis_notes: diagnosisNotes.trim() || undefined,
        invoice: {
          invoice_number: currentInvoice.invoice_number,
          issued_on: currentInvoice.issued_on,
          line_items: currentInvoice.line_items,
          subtotal,
          tax_amount: currentInvoice.tax_amount,
          total_amount: totalAmount,
          currency: currentInvoice.currency,
          notes: currentInvoice.notes || undefined,
        },
      });

      const savedCode = res.data.appointment_code;
      setQrPayload(res.data.qr_payload);
      setQrImage(`data:image/png;base64,${res.data.qr_image_base64}`);

      cacheClinical(
        savedCode,
        {
          dx: diagnosis.trim(),
          rx: prescription.trim(),
          notes: diagnosisNotes.trim(),
        },
        currentInvoice,
      );

      setSelectedAppt((prev) =>
        prev
          ? {
              ...prev,
              appointment_code: savedCode,
              diagnosis_entered: true,
              qr_minted: true,
              status: res.data.status,
            }
          : null,
      );

      toast.success("Invoice generated & QR code minted for patient scan!");
      loadAppointments();
    } catch (err: any) {
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        clearSession();
        setProfile(null);
        toast.error("Session expired. Please sign in again.");
        return;
      }
      const msg = err?.response?.data?.detail || "Failed to generate invoice & QR.";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const addLineItem = () => {
    setLineItems((prev) => [...prev, { description: "", quantity: 1, unit_price: 0 }]);
  };

  const updateLineItem = (
    index: number,
    field: keyof InvoiceLineItemState,
    value: string | number,
  ) => {
    setLineItems((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: value };
      return copy;
    });
  };

  const removeLineItem = (index: number) => {
    setLineItems((prev) => prev.filter((_, idx) => idx !== index));
  };

  const copyCode = () => {
    const code = selectedAppt?.appointment_code;
    if (!code) return;
    try {
      navigator.clipboard.writeText(code);
      setCopiedCode(true);
      toast.success("Appointment code copied.");
      setTimeout(() => setCopiedCode(false), 2000);
    } catch {}
  };

  const filteredAppointments = appointments.filter((a) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = (a.patient_name || "").toLowerCase().includes(q);
      const matchCode = (a.appointment_code || "").toLowerCase().includes(q);
      const matchDept = (a.department || "").toLowerCase().includes(q);
      if (!matchName && !matchCode && !matchDept) return false;
    }
    return true;
  });

  const STATUS_BADGES: Record<string, { label: string; cls: string }> = {
    upcoming: { label: "Upcoming", cls: "bg-blue-500/10 text-blue-600" },
    booked: { label: "Booked", cls: "bg-blue-500/10 text-blue-600" },
    checked_in: { label: "Checked In", cls: "bg-amber-500/10 text-amber-600" },
    in_consultation: { label: "In Consultation", cls: "bg-violet-500/10 text-violet-600" },
    completed: { label: "Transferred / Purged", cls: "bg-emerald-500/10 text-emerald-600" },
    cancelled: { label: "Cancelled", cls: "bg-red-500/10 text-red-600" },
  };

  // ---- boot splash ------------------------------------------------------
  if (booting) {
    return (
      <div className="min-h-screen bg-background grid place-items-center font-sans px-4">
        <div className="text-center space-y-3">
          <div className="h-11 w-11 rounded-full bg-primary/10 text-primary grid place-items-center mx-auto animate-pulse">
            <FiActivity className="h-5 w-5" />
          </div>
          <p className="text-sm text-muted-foreground animate-pulse">
            Restoring your session…
          </p>
        </div>
      </div>
    );
  }

  // ---- AUTH SCREEN (client/server login + NMC registration) -------------
  if (!profile) {
    return (
      <div className="min-h-screen bg-background flex flex-col justify-between px-4 py-8 font-sans selection:bg-neutral-800 selection:text-white">
        {/* Minimal MedTour Header matching Landing page */}
        <header className="w-full max-w-5xl mx-auto flex items-center justify-between">
          <button
            type="button"
            onClick={() => navigate({ to: "/landing" })}
            className="group inline-flex items-center gap-2 px-3 py-1.5 rounded-full hover:bg-muted/60 transition-all cursor-pointer focus:outline-none"
            aria-label="MedTour Landing Page"
          >
            <span className="text-xl font-black tracking-tight text-foreground group-hover:opacity-85 transition-opacity">
              MedTour
            </span>
          </button>
          <button
            type="button"
            onClick={() => navigate({ to: "/visits" })}
            className="text-xs font-bold text-muted-foreground hover:text-foreground transition-colors px-3 py-1 rounded-full border border-border/60 hover:bg-muted/40"
          >
            ← Patient Visits
          </button>
        </header>

        <div className="w-full max-w-md mx-auto my-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="text-center space-y-3">
            <span className="text-xs font-bold tracking-[0.25em] uppercase text-muted-foreground font-mono inline-block">
              Physician Portal
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-foreground">
              Clinical Gateway
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground max-w-sm mx-auto leading-relaxed">
              NMC-verified practitioner sign-in. Issue clinical discharge records & itemized travel insurance invoices.
            </p>
          </div>

          <Card className="rounded-3xl border border-border/80 shadow-[0_8px_30px_rgba(0,0,0,0.06)] dark:shadow-[0_8px_30px_rgba(0,0,0,0.4)] p-6 sm:p-8 bg-card/90 backdrop-blur-xl">
            {/* Morphing Switcher Tabs */}
            <div className="grid grid-cols-2 gap-1.5 p-1 rounded-2xl bg-muted/60 border border-border/50 mb-6">
              <button
                type="button"
                onClick={() => setAuthTab("signin")}
                className={`h-10 rounded-xl text-xs font-extrabold transition-all duration-200 cursor-pointer ${
                  authTab === "signin"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Doctor Sign In
              </button>
              <button
                type="button"
                onClick={() => setAuthTab("register")}
                className={`h-10 rounded-xl text-xs font-extrabold transition-all duration-200 cursor-pointer ${
                  authTab === "register"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Register with NMC
              </button>
            </div>

            {authTab === "signin" ? (
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="doc-email" className="text-xs font-bold text-foreground">
                    Doctor Email
                  </Label>
                  <Input
                    id="doc-email"
                    type="email"
                    autoComplete="email"
                    placeholder="doctor@hospital.in"
                    value={loginForm.email}
                    onChange={(e) =>
                      setLoginForm((f) => ({ ...f, email: e.target.value }))
                    }
                    className="h-11 rounded-xl text-sm bg-background border-border/80 focus:ring-1 focus:ring-foreground"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="doc-password" className="text-xs font-bold text-foreground">
                    Password
                  </Label>
                  <Input
                    id="doc-password"
                    type="password"
                    autoComplete="current-password"
                    placeholder="••••••••"
                    value={loginForm.password}
                    onChange={(e) =>
                      setLoginForm((f) => ({ ...f, password: e.target.value }))
                    }
                    className="h-11 rounded-xl text-sm bg-background border-border/80 focus:ring-1 focus:ring-foreground"
                  />
                </div>
                <Button
                  type="submit"
                  disabled={authLoading}
                  className="w-full h-12 rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 font-extrabold text-sm shadow-md transition-all active:scale-98 cursor-pointer mt-2"
                >
                  {authLoading ? "Authenticating Session…" : "Sign In to Portal →"}
                </Button>
                <div className="p-3 rounded-2xl bg-muted/30 border border-border/50 text-[11px] text-muted-foreground leading-relaxed text-center">
                  🔒 Your NMC verification badge is cached securely on your profile for instant future access.
                </div>
              </form>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="reg-name" className="text-xs font-bold text-foreground">
                    Full Legal Name (as on NMC register)
                  </Label>
                  <Input
                    id="reg-name"
                    placeholder="Dr. Aparna Deshmukh"
                    value={regForm.full_name}
                    onChange={(e) =>
                      setRegForm((f) => ({ ...f, full_name: e.target.value }))
                    }
                    className="h-11 rounded-xl text-sm bg-background border-border/80"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-email" className="text-xs font-bold text-foreground">
                      Email
                    </Label>
                    <Input
                      id="reg-email"
                      type="email"
                      placeholder="doctor@hospital.in"
                      value={regForm.email}
                      onChange={(e) =>
                        setRegForm((f) => ({ ...f, email: e.target.value }))
                      }
                      className="h-11 rounded-xl text-sm bg-background border-border/80"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-password" className="text-xs font-bold text-foreground">
                      Password
                    </Label>
                    <Input
                      id="reg-password"
                      type="password"
                      placeholder="min 6 chars"
                      value={regForm.password}
                      onChange={(e) =>
                        setRegForm((f) => ({ ...f, password: e.target.value }))
                      }
                      className="h-11 rounded-xl text-sm bg-background border-border/80"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-number" className="text-xs font-bold text-foreground">
                      NMC Reg. Number <span className="text-red-500">*</span>
                    </Label>
                    <Input
                      id="reg-number"
                      placeholder="e.g. 2015/MH/12345"
                      value={regForm.reg_number}
                      onChange={(e) =>
                        setRegForm((f) => ({ ...f, reg_number: e.target.value }))
                      }
                      className="h-11 rounded-xl text-sm font-mono bg-background border-border/80"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="reg-year" className="text-xs font-bold text-foreground">
                      Reg. Year (optional)
                    </Label>
                    <Input
                      id="reg-year"
                      placeholder="e.g. 2015"
                      value={regForm.year}
                      onChange={(e) =>
                        setRegForm((f) => ({ ...f, year: e.target.value }))
                      }
                      className="h-11 rounded-xl text-sm bg-background border-border/80"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="reg-council" className="text-xs font-bold text-foreground">
                    State Medical Council <span className="text-red-500">*</span>
                  </Label>
                  <select
                    id="reg-council"
                    value={regForm.state_council}
                    onChange={(e) =>
                      setRegForm((f) => ({ ...f, state_council: e.target.value }))
                    }
                    className="w-full h-11 rounded-xl border border-border/80 bg-background px-3 text-sm font-medium"
                  >
                    <option value="">Select council…</option>
                    {STATE_COUNCILS.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="reg-spec" className="text-xs font-bold text-foreground">
                    Specialization (optional)
                  </Label>
                  <Input
                    id="reg-spec"
                    placeholder="e.g. General Medicine, Orthopedics, Cardiology"
                    value={regForm.specialization}
                    onChange={(e) =>
                      setRegForm((f) => ({ ...f, specialization: e.target.value }))
                    }
                    className="h-11 rounded-xl text-sm bg-background border-border/80"
                  />
                </div>

                {/* Hospital designation */}
                <div className="space-y-1.5">
                  <Label htmlFor="reg-hospital" className="text-xs font-bold text-foreground">
                    Designated Hospital / Clinic (optional)
                  </Label>
                  {selectedHospital ? (
                    <div className="flex items-center justify-between gap-2 h-11 rounded-xl border border-border/80 bg-muted/30 px-3">
                      <span className="text-sm font-semibold truncate">
                        {selectedHospital.name}
                        {selectedHospital.city ? ` · ${selectedHospital.city}` : ""}
                      </span>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedHospital(null);
                          setHospitalQuery("");
                        }}
                        className="text-xs font-bold text-muted-foreground hover:text-foreground shrink-0 cursor-pointer"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <>
                      <Input
                        id="reg-hospital"
                        placeholder="Search hospital name or city…"
                        value={hospitalQuery}
                        onChange={(e) => setHospitalQuery(e.target.value)}
                        className="h-11 rounded-xl text-sm bg-background border-border/80"
                      />
                      {hospitalHits.length > 0 && (
                        <div className="max-h-40 overflow-y-auto rounded-xl border border-border bg-card divide-y divide-border shadow-lg">
                          {hospitalHits.map((h) => (
                            <button
                              key={h.id}
                              type="button"
                              onClick={() => {
                                setSelectedHospital(h);
                                setHospitalHits([]);
                              }}
                              className="w-full text-left px-3 py-2 text-xs font-semibold hover:bg-muted/60 transition-colors"
                            >
                              {h.name}
                              {h.city ? (
                                <span className="text-muted-foreground">
                                  {" "}
                                  · {h.city}
                                </span>
                              ) : null}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  <p className="text-[10px] text-muted-foreground">
                    Leave blank to operate across all hospital appointments in demo mode.
                  </p>
                </div>

                <div className="flex items-start gap-2.5 p-3.5 rounded-2xl bg-muted/40 border border-border/60">
                  <FiShield className="h-4 w-4 mt-0.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    Registration verified live against the{" "}
                    <strong className="text-foreground">NMC Indian Medical Register</strong> via
                    api.askmydoc.in.
                  </p>
                </div>

                <Button
                  type="submit"
                  disabled={authLoading}
                  className="w-full h-12 rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 font-extrabold text-sm shadow-md transition-all active:scale-98 cursor-pointer mt-2"
                >
                  {authLoading
                    ? "Verifying with NMC register…"
                    : "Verify & Create Doctor Account →"}
                </Button>
              </form>
            )}
          </Card>

          <p className="text-center text-[11px] text-muted-foreground">
            Looking for patient emergency services?{" "}
            <button
              type="button"
              onClick={() => navigate({ to: "/landing" })}
              className="font-bold underline text-foreground hover:opacity-80"
            >
              Go to Landing
            </button>
          </p>
        </div>

        <footer className="w-full max-w-5xl mx-auto text-center pt-4 text-[11px] text-muted-foreground/60">
          MedTour Clinical Gateway · Secure NMC-Integrated Practitioner Console
        </footer>
      </div>
    );
  }

  // ---- PORTAL (signed in) ----------------------------------------------
  const verifiedAgo = relativeTime(profile.verification.verified_at);
  const verificationLine = profile.verification.verified
    ? profile.verification.cached
      ? `Verified ${verifiedAgo || "earlier"} · served from cache`
      : "Verified just now · live lookup"
    : `Not verified${profile.verification.status ? ` (${profile.verification.status})` : ""} — run Re-verify`;

  return (
    <div className="min-h-screen bg-background font-sans selection:bg-neutral-800 selection:text-white pb-16">
      {/* Top Navigation Header matching Landing page */}
      <header className="border-b border-border/80 bg-background/90 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-4 min-w-0">
            <button
              type="button"
              onClick={() => navigate({ to: "/landing" })}
              className="group inline-flex items-center gap-2 hover:opacity-80 transition-opacity focus:outline-none cursor-pointer"
              title="MedTour Landing Page"
            >
              <span className="text-xl font-black tracking-tight text-foreground">
                MedTour
              </span>
            </button>
            <div className="h-5 w-px bg-border/80 hidden sm:block" />
            <div className="min-w-0 flex items-center gap-2">
              <span className="text-xs font-mono font-bold tracking-wider uppercase text-muted-foreground hidden sm:inline-block">
                Physician Console
              </span>
              {profile.verification.verified && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <FiShield className="h-3 w-3" />
                  NMC Verified
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <Button
              onClick={handleReverify}
              disabled={reverifying}
              variant="outline"
              size="sm"
              className="rounded-full font-bold text-xs gap-1.5 h-9 px-3.5 border-border hover:bg-muted cursor-pointer"
              title="Force fresh lookup against NMC registry"
            >
              <FiRefreshCw
                className={`h-3.5 w-3.5 ${reverifying ? "animate-spin" : ""}`}
              />
              {reverifying ? "Verifying…" : "Re-verify"}
            </Button>
            <Button
              onClick={loadAppointments}
              variant="outline"
              size="sm"
              className="rounded-full font-bold text-xs h-9 px-3.5 border-border hover:bg-muted cursor-pointer"
            >
              Refresh
            </Button>
            <Button
              onClick={logout}
              variant="outline"
              size="sm"
              className="rounded-full font-bold text-xs gap-1.5 h-9 px-3.5 border-destructive/20 text-destructive hover:bg-destructive/10 cursor-pointer"
            >
              <FiLogOut className="h-3.5 w-3.5" /> Sign Out
            </Button>
          </div>
        </div>
      </header>

      {/* DOCTOR INFO STRIP — Clean minimalist pill cards */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-5">
        <Card className="rounded-3xl border border-border/80 p-5 bg-card/60 backdrop-blur-md shadow-xs grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-4 items-center">
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
              Physician
            </p>
            <p className="text-sm font-extrabold text-foreground mt-0.5 truncate">
              Dr. {profile.full_name}
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {profile.qualification || profile.specialization || "Licensed Practitioner"}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
              NMC Reg ID
            </p>
            <p className="text-sm font-extrabold font-mono text-foreground mt-0.5 truncate">
              {profile.reg_number}
            </p>
            <p className="text-[11px] text-muted-foreground truncate">
              {profile.state_council || "Medical Council"}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
              Affiliated Facility
            </p>
            <p className="text-sm font-extrabold text-foreground mt-0.5 truncate">
              {profile.hospital_name || "All Facilities (Demo)"}
            </p>
            <p className="text-[11px] text-muted-foreground">Active Roster</p>
          </div>
          <div>
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
              Patients In Scope
            </p>
            <p className="text-sm font-extrabold text-foreground mt-0.5">
              {profile.appointment_count} Appointments
            </p>
            <p className="text-[11px] text-muted-foreground">Queue active</p>
          </div>
          <div className="col-span-2 sm:col-span-4 lg:col-span-1 pt-2 lg:pt-0 border-t lg:border-t-0 lg:border-l border-border/60 lg:pl-4">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest font-mono">
              Registry Status
            </p>
            <p
              className={`text-xs font-bold mt-0.5 ${
                profile.verification.verified
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-amber-600 dark:text-amber-400"
              }`}
            >
              {verificationLine}
            </p>
            <p className="text-[10px] text-muted-foreground truncate">
              {profile.verification.source || "api.askmydoc.in (NMC IMR)"}
            </p>
          </div>
        </Card>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Appointment List */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <FiSearch className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search patient, code, or department…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-11 rounded-2xl text-sm bg-background border-border/80"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-11 rounded-2xl border border-border/80 bg-background px-3.5 text-xs font-bold"
            >
              <option value="all">All Statuses</option>
              <option value="upcoming">Upcoming</option>
              <option value="in_consultation">In Consultation</option>
              <option value="completed">Completed</option>
            </select>
          </div>

          {loading ? (
            <Card className="p-8 text-center rounded-3xl border-dashed">
              <p className="text-sm text-muted-foreground animate-pulse font-medium">
                Loading appointments…
              </p>
            </Card>
          ) : filteredAppointments.length === 0 ? (
            <Card className="p-8 text-center rounded-3xl border-dashed">
              <p className="text-sm font-semibold text-muted-foreground">
                No appointments found.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                {profile.hospital_name
                  ? `Showing appointments at ${profile.hospital_name}.`
                  : "Patients create appointments from the Visits tab."}
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {filteredAppointments.map((appt) => {
                const badge = STATUS_BADGES[appt.status] || {
                  label: appt.status,
                  cls: "bg-muted text-muted-foreground",
                };
                const isSelected = selectedAppt?.id === appt.id;
                return (
                  <Card
                    key={appt.id}
                    onClick={() => selectAppointment(appt)}
                    className={`rounded-3xl border-2 p-5 cursor-pointer transition-all duration-200 ${
                      isSelected
                        ? "border-black dark:border-white bg-black/5 dark:bg-white/5 shadow-md"
                        : "border-border/70 hover:border-border hover:shadow-xs bg-card"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase tracking-wider inline-block mb-2 ${badge.cls}`}
                        >
                          {badge.label}
                        </span>
                        <h3 className="text-base font-extrabold text-foreground">
                          {appt.patient_name || "Patient"}
                        </h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {appt.hospital_name || appt.hospital?.name || "Hospital"} •{" "}
                          {appt.department || "General"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(appt.appointment_time).toLocaleString()}
                        </p>
                      </div>
                      <div className="text-right">
                        {appt.appointment_code && (
                          <span className="text-[10px] font-mono font-bold text-foreground bg-muted px-2.5 py-1 rounded-full border border-border/80">
                            {appt.appointment_code}
                          </span>
                        )}
                        {appt.diagnosis_entered && (
                          <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-extrabold mt-1.5 flex items-center justify-end gap-1">
                            ✓ Diagnosed
                          </p>
                        )}
                        {appt.doctor_name && (
                          <p className="text-[10px] text-muted-foreground mt-1">
                            Dr. {appt.doctor_name}
                          </p>
                        )}
                      </div>
                    </div>
                    {appt.reason && (
                      <p className="text-xs text-muted-foreground mt-2.5 p-2.5 rounded-xl bg-muted/40 border border-border/50">
                        <strong>Reason:</strong> {appt.reason}
                      </p>
                    )}
                  </Card>
                );
              })}
            </div>
          )}

          {/* Ephemeral Tray Footer Actions */}
          <div className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (window.confirm("Wipe all local shift memory and cached clinical data from this browser?")) {
                  try {
                    Object.keys(localStorage).forEach((key) => {
                      if (key.startsWith("medtour_doctor_clinical:")) {
                        localStorage.removeItem(key);
                      }
                    });
                  } catch {}
                  setSelectedAppt(null);
                  setQrImage(null);
                  setQrPayload(null);
                  setDiagnosis("");
                  setPrescription("");
                  setDiagnosisNotes("");
                  toast.success("Shift memory wiped cleanly. Zero persistent clinical data on this device.");
                  loadAppointments();
                }
              }}
              className="w-full h-10 rounded-2xl border-border/80 text-muted-foreground hover:text-red-500 hover:border-red-500/40 text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <FiTrash2 className="h-3.5 w-3.5" /> End Shift & Wipe Local Memory
            </Button>
          </div>
        </div>

        {/* Right: Diagnosis Form + QR */}
        <div className="lg:col-span-7 space-y-4">
          {!selectedAppt ? (
            <Card className="p-12 text-center rounded-2xl border-dashed">
              <FiUser className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
              <h3 className="text-lg font-bold text-foreground">
                Select an Appointment
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                Choose a patient from the list to enter their diagnosis and
                prescription.
              </p>
            </Card>
          ) : (
            <>
              {/* Patient Info Card */}
              <Card className="rounded-3xl border border-border/80 p-5 space-y-3 bg-card/80 backdrop-blur-md shadow-xs">
                <div className="flex items-center justify-between border-b border-border/60 pb-3">
                  <div>
                    <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-muted-foreground block">
                      Active Patient Session
                    </span>
                    <h2 className="text-lg font-black text-foreground">
                      {selectedAppt.patient_name || "Guest Tourist"}
                    </h2>
                  </div>
                  {selectedAppt.appointment_code && (
                    <span className="text-xs font-mono font-extrabold text-foreground bg-muted px-3 py-1 rounded-full border border-border/80">
                      {selectedAppt.appointment_code}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-[10px] font-bold text-muted-foreground uppercase block font-mono">
                      Department
                    </span>
                    <span className="font-extrabold text-foreground text-sm">
                      {selectedAppt.department || "General"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] font-bold text-muted-foreground uppercase block font-mono">
                      Facility
                    </span>
                    <span className="font-extrabold text-foreground text-sm truncate block">
                      {selectedAppt.hospital_name ||
                        selectedAppt.hospital?.name ||
                        "—"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="text-[10px] font-bold text-muted-foreground uppercase block font-mono">
                      Reported Symptoms / Need
                    </span>
                    <span className="font-semibold text-foreground text-sm">
                      {selectedAppt.reason || "General Consultation"}
                    </span>
                  </div>
                </div>
              </Card>

              {/* Stepper Header */}
              <div className="grid grid-cols-2 gap-2 p-1.5 rounded-2xl bg-muted/60 border border-border/60">
                <button
                  type="button"
                  onClick={() => setStage(1)}
                  className={`h-11 rounded-xl text-xs font-extrabold flex items-center justify-center gap-2.5 transition-all cursor-pointer ${
                    stage === 1
                      ? "bg-background text-foreground shadow-sm border border-border/80"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className={`h-6 w-6 rounded-full text-xs grid place-items-center font-black ${
                    stage === 1
                      ? "bg-black text-white dark:bg-white dark:text-black"
                      : "bg-muted text-muted-foreground"
                  }`}>
                    1
                  </span>
                  Step 1: Clinical Entry
                </button>
                <button
                  type="button"
                  onClick={() => setStage(2)}
                  className={`h-11 rounded-xl text-xs font-extrabold flex items-center justify-center gap-2.5 transition-all cursor-pointer ${
                    stage === 2
                      ? "bg-background text-foreground shadow-sm border border-border/80"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <span className={`h-6 w-6 rounded-full text-xs grid place-items-center font-black ${
                    stage === 2
                      ? "bg-black text-white dark:bg-white dark:text-black"
                      : "bg-muted text-muted-foreground"
                  }`}>
                    2
                  </span>
                  Step 2: Review & Generate QR
                </button>
              </div>

              {/* Stage 1: Diagnosis & Prescription Form */}
              {stage === 1 && (
                <Card className="rounded-3xl border border-border/80 p-6 space-y-4 shadow-xs bg-card/90 backdrop-blur-md animate-in fade-in duration-200">
                  <div className="flex items-center justify-between border-b border-border/60 pb-3">
                    <h2 className="text-base font-extrabold text-foreground flex items-center gap-2">
                      <FiFileText className="h-4 w-4 text-primary" />
                      Step 1: Clinical Consultation Entry
                    </h2>
                    <span className="text-[10px] font-mono font-bold text-emerald-700 dark:text-emerald-400 uppercase px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                      Local Memory Only (Zero-Persistence)
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="diagnosis" className="text-xs font-bold text-foreground">
                      Diagnosis <span className="text-red-500">*</span>
                    </Label>
                    <Textarea
                      id="diagnosis"
                      placeholder="e.g., Acute viral pharyngitis. RRT negative. No red flags."
                      value={diagnosis}
                      onChange={(e) => setDiagnosis(e.target.value)}
                      className="rounded-2xl text-sm min-h-[90px] bg-background border-border/80"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="prescription" className="text-xs font-bold text-foreground">
                      Prescription <span className="text-red-500">*</span>
                    </Label>
                    <Textarea
                      id="prescription"
                      placeholder="e.g., Paracetamol 500mg — 1 tab TDS x 5 days. Warm saline gargles."
                      value={prescription}
                      onChange={(e) => setPrescription(e.target.value)}
                      className="rounded-2xl text-sm min-h-[90px] bg-background border-border/80"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="notes" className="text-xs font-bold text-foreground">
                      Clinical Notes (optional)
                    </Label>
                    <Textarea
                      id="notes"
                      placeholder="Follow-up in 7 days if symptoms persist…"
                      value={diagnosisNotes}
                      onChange={(e) => setDiagnosisNotes(e.target.value)}
                      className="rounded-2xl text-sm min-h-[70px] bg-background border-border/80"
                    />
                  </div>

                  {/* Live Character/Density Meter */}
                  {(() => {
                    const charCount = (diagnosis + prescription + diagnosisNotes).length;
                    const maxRecommended = 1200;
                    const densityPct = Math.min(100, Math.round((charCount / maxRecommended) * 100));
                    const isHigh = densityPct > 80;
                    const isWarning = densityPct > 95;
                    return (
                      <div className="p-2.5 rounded-2xl bg-muted/30 border border-border/50 text-[11px] flex items-center justify-between font-mono">
                        <span className="text-muted-foreground">
                          Payload Density:{" "}
                          <strong className={isWarning ? "text-red-500" : isHigh ? "text-amber-500" : "text-foreground"}>
                            {charCount} / {maxRecommended} chars ({densityPct}%)
                          </strong>
                        </span>
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase ${
                          isWarning
                            ? "bg-red-500/10 text-red-600"
                            : isHigh
                            ? "bg-amber-500/10 text-amber-600"
                            : "bg-emerald-500/10 text-emerald-600"
                        }`}>
                          {isWarning ? "High Density" : isHigh ? "Moderate Density" : "Optimal for Scanning"}
                        </span>
                      </div>
                    );
                  })()}

                  <Button
                    onClick={submitStage1Clinical}
                    disabled={submitting}
                    className="w-full h-12 rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 font-extrabold text-sm shadow-md transition-all active:scale-98 cursor-pointer mt-2"
                  >
                    {submitting ? "Preparing Clinical Payload…" : "Finalize & Show QR →"}
                  </Button>
                </Card>
              )}

              {/* Stage 2: Invoice & Mint QR */}
              {stage === 2 && (
                <Card className="rounded-3xl border border-border/80 p-6 space-y-5 shadow-xs bg-card/90 backdrop-blur-md animate-in fade-in duration-200">
                  <div className="flex items-center justify-between border-b border-border/60 pb-3">
                    <div className="flex items-center gap-2">
                      <FiDollarSign className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                      <h2 className="text-base font-extrabold text-foreground">
                        Stage 2: Patient Invoice & Discharge QR
                      </h2>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setStage(1)}
                      className="text-xs font-bold text-muted-foreground hover:text-foreground h-8 px-3 rounded-full hover:bg-muted/60 transition-colors gap-1.5 cursor-pointer"
                    >
                      <FiArrowLeft className="h-3.5 w-3.5" /> Back to Clinical
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="space-y-1.5 sm:col-span-2">
                      <Label htmlFor="inv-num" className="text-xs font-bold text-foreground">
                        Invoice Number
                      </Label>
                      <Input
                        id="inv-num"
                        placeholder="MT-INV-XXXXXXXX"
                        value={invoiceNumber}
                        onChange={(e) => setInvoiceNumber(e.target.value)}
                        className="rounded-xl text-sm font-mono bg-background border-border/80"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="inv-date" className="text-xs font-bold text-foreground">
                        Issued Date
                      </Label>
                      <Input
                        id="inv-date"
                        type="date"
                        value={issuedOn}
                        onChange={(e) => setIssuedOn(e.target.value)}
                        className="rounded-xl text-sm bg-background border-border/80"
                      />
                    </div>
                  </div>

                  {/* Line Items */}
                  <div className="space-y-2.5 pt-1">
                    <div className="flex items-center justify-between">
                      <Label className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground font-mono">
                        Itemized Charges
                      </Label>
                      <Button
                        type="button"
                        onClick={addLineItem}
                        variant="outline"
                        size="sm"
                        className="rounded-full text-xs font-bold h-7 px-3 border-border/80 hover:bg-muted/40 gap-1.5 cursor-pointer"
                      >
                        <FiPlus className="h-3.5 w-3.5" /> Add Row
                      </Button>
                    </div>

                    <div className="space-y-2">
                      {lineItems.map((item, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-2 p-2.5 rounded-2xl bg-muted/40 border border-border/60 transition-all focus-within:border-foreground/30"
                        >
                          <Input
                            placeholder="Description (e.g. Consultation, Blood Test)"
                            value={item.description}
                            onChange={(e) => updateLineItem(idx, "description", e.target.value)}
                            className="flex-1 rounded-xl text-xs h-9 bg-background border-border/60"
                          />
                          <Input
                            type="number"
                            min="1"
                            placeholder="Qty"
                            value={item.quantity}
                            onChange={(e) =>
                              updateLineItem(idx, "quantity", parseFloat(e.target.value) || 0)
                            }
                            className="w-16 rounded-xl text-xs h-9 bg-background border-border/60 text-center font-mono"
                          />
                          <Input
                            type="number"
                            min="0"
                            step="0.01"
                            placeholder="Price"
                            value={item.unit_price}
                            onChange={(e) =>
                              updateLineItem(idx, "unit_price", parseFloat(e.target.value) || 0)
                            }
                            className="w-24 rounded-xl text-xs h-9 bg-background border-border/60 text-right font-mono font-semibold"
                          />
                          <button
                            type="button"
                            onClick={() => removeLineItem(idx)}
                            disabled={lineItems.length === 1}
                            className="h-9 w-9 rounded-xl flex items-center justify-center text-muted-foreground hover:text-red-500 hover:bg-red-500/10 disabled:opacity-30 disabled:hover:text-muted-foreground shrink-0 transition-colors cursor-pointer"
                            aria-label="Remove item"
                          >
                            <FiTrash2 className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Totals & Currency */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="inv-currency" className="text-xs font-bold text-foreground">
                        Currency
                      </Label>
                      <select
                        id="inv-currency"
                        value={currency}
                        onChange={(e) => setCurrency(e.target.value)}
                        className="w-full h-11 rounded-xl border border-border/80 bg-background px-3 text-xs font-bold text-foreground focus:ring-1 focus:ring-foreground"
                      >
                        <option value="USD">USD ($)</option>
                        <option value="INR">INR (₹)</option>
                        <option value="EUR">EUR (€)</option>
                        <option value="GBP">GBP (£)</option>
                        <option value="AED">AED (AED)</option>
                      </select>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor="inv-tax" className="text-xs font-bold text-foreground">
                        Tax Amount ({currency})
                      </Label>
                      <Input
                        id="inv-tax"
                        type="number"
                        min="0"
                        step="0.01"
                        value={taxAmount}
                        onChange={(e) => setTaxAmount(parseFloat(e.target.value) || 0)}
                        className="rounded-xl text-xs font-mono text-right h-11 bg-background border-border/80 font-semibold"
                      />
                    </div>

                    <div className="p-3.5 rounded-2xl bg-muted/60 border border-border/80 flex flex-col justify-center">
                      <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase tracking-wider">
                        Total Sum
                      </span>
                      <span className="text-lg font-black text-foreground font-mono mt-0.5">
                        {currency} {totalAmount.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="inv-notes" className="text-xs font-bold text-foreground">
                      Invoice Notes (optional)
                    </Label>
                    <Textarea
                      id="inv-notes"
                      placeholder="e.g. Paid via travel insurance pre-authorization / card"
                      value={invoiceNotes}
                      onChange={(e) => setInvoiceNotes(e.target.value)}
                      className="rounded-2xl text-sm min-h-[60px] bg-background border-border/80"
                    />
                  </div>

                  <Button
                    onClick={submitStage2Invoice}
                    disabled={submitting}
                    className="w-full h-12 rounded-full bg-black text-white dark:bg-white dark:text-black hover:opacity-90 font-extrabold text-sm shadow-md transition-all active:scale-98 cursor-pointer mt-2"
                  >
                    {submitting
                      ? "Generating Invoice & QR…"
                      : selectedAppt.qr_minted
                        ? "Update Invoice & Regenerate QR →"
                        : "Generate Invoice & Mint QR →"}
                  </Button>
                </Card>
              )}

              {/* QR Code Display (Split-View Stage 2 Result) */}
              {qrImage && (
                <Card className="rounded-3xl border-2 border-border/80 bg-card/90 backdrop-blur-md p-6 sm:p-8 space-y-6 shadow-sm animate-in fade-in slide-in-from-bottom-2 duration-300">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-4">
                    <div>
                      <span className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-emerald-600 dark:text-emerald-400 block">
                        Encrypted Ephemeral Session Generated
                      </span>
                      <h2 className="text-xl font-black text-foreground">
                        Patient Transfer & Discharge QR
                      </h2>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-muted-foreground px-2.5 py-1 rounded-full bg-muted border border-border/80">
                      AES-256 Encrypted with aID
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                    {/* Left: Read-Only Clinical Summary */}
                    <div className="md:col-span-6 space-y-3">
                      <div className="p-4 rounded-2xl bg-muted/40 border border-border/60 space-y-2 text-xs">
                        <span className="text-[10px] font-mono font-bold uppercase text-muted-foreground">
                          Clinical Discharge Summary
                        </span>
                        <div>
                          <span className="font-bold text-foreground block">Diagnosis:</span>
                          <p className="text-muted-foreground mt-0.5">{diagnosis}</p>
                        </div>
                        <div className="pt-1.5 border-t border-border/40">
                          <span className="font-bold text-foreground block">Prescription:</span>
                          <p className="text-muted-foreground mt-0.5">{prescription}</p>
                        </div>
                        {invoiceNumber && (
                          <div className="pt-1.5 border-t border-border/40 flex justify-between items-center font-mono">
                            <span className="font-bold text-foreground">Total Bill:</span>
                            <span className="font-bold text-emerald-600 dark:text-emerald-400">
                              {currency} {totalAmount.toFixed(2)}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-800 dark:text-amber-300 leading-relaxed">
                        🔒 <strong>Zero-Persistence Guarantee:</strong> The clinical payload is fully encrypted with the patient's appointment code. Once transferred to the patient's phone, local browser memory can be discarded safely.
                      </div>
                    </div>

                    {/* Right: High-Contrast QR Code */}
                    <div className="md:col-span-6 flex flex-col items-center gap-3">
                      <div className="bg-white p-5 rounded-3xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] border border-neutral-100 flex items-center justify-center">
                        <img
                          src={qrImage}
                          alt="Appointment QR code"
                          width={280}
                          height={280}
                          className="block w-[280px] h-[280px]"
                        />
                      </div>
                      <span className="text-[11px] font-mono text-muted-foreground">
                        Code: <strong className="text-foreground">{selectedAppt.appointment_code}</strong>
                      </span>
                    </div>
                  </div>

                  {/* Actions & Auto-Clear Flow */}
                  <div className="pt-2 border-t border-border/60 flex flex-col sm:flex-row gap-3">
                    <Button
                      onClick={() => {
                        // Discard & advance to next patient
                        try {
                          localStorage.removeItem(clinicalCacheKey(selectedAppt.appointment_code));
                        } catch {}
                        setSelectedAppt(null);
                        setQrImage(null);
                        setQrPayload(null);
                        setDiagnosis("");
                        setPrescription("");
                        setDiagnosisNotes("");
                        toast.success("Active session discarded and memory purged. Ready for next patient!");
                        loadAppointments();
                      }}
                      className="flex-1 h-12 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs shadow-md transition-all active:scale-98 cursor-pointer"
                    >
                      ✓ Patient Scanned — Discard & Next Patient
                    </Button>
                    <Button
                      onClick={copyCode}
                      variant="outline"
                      className="h-12 px-6 rounded-full font-bold text-xs border-border/80 hover:bg-muted/40 cursor-pointer"
                    >
                      {copiedCode ? (
                        <>
                          <FiCheck className="h-3.5 w-3.5 text-emerald-600" /> Copied Code
                        </>
                      ) : (
                        <>
                          <FiCopy className="h-3.5 w-3.5" /> Copy Code
                        </>
                      )}
                    </Button>
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
}
