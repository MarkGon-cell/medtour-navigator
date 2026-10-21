import { createFileRoute, useNavigate, useSearch } from "@tanstack/react-router";
import { useState, useEffect, useMemo } from "react";
import { MobileNav } from "@/components/site/MobileNav";
import { QuickMedicalIdModal, getStoredMedicalId } from "@/components/site/QuickMedicalIdModal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FiClock, FiCheck, FiX, FiDownload, FiShield, FiCamera, FiEye, FiFileText, FiDollarSign, FiTrash2 } from "react-icons/fi";
import { toast } from "sonner";
import { QrScannerModal } from "@/components/visits/QrScannerModal";
import { ClaimPurchaseModal } from "@/components/visits/ClaimPurchaseModal";
import { getPatientName } from "@/lib/mtrSession";
import { promptMtrBackup } from "@/components/site/MtrBackupPrompt";
import { QRCodeSVG } from "qrcode.react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/visits")({
  validateSearch: (search: Record<string, unknown>): { tab?: string } => {
    return {
      tab: (search.tab as string) || "upcoming",
    };
  },
  head: () => ({
    meta: [
      { title: "My Visits & Insurance Receipts | MedTour" },
      { name: "description", content: "3-tab visit ledger with offline client-side insurance-ready PDF receipt generation." },
    ],
  }),
  component: VisitsPage,
});

export interface VisitRecord {
  id: string;
  facilityName: string;
  address: string;
  phone: string;
  status: "upcoming" | "completed" | "cancelled";
  timestamp: number;
  symptoms: string[];
  cost: string;
  insuranceTaxId: string;
  estimatedWaitMins?: number;
  cancellationReason?: string;
  // Doctor diagnosis & prescription (via QR scan)
  appointmentCode?: string;
  diagnosis?: string;
  prescription?: string;
  diagnosisNotes?: string;
  completedAt?: string;
  department?: string;
  /** Patient name as sent at booking (no patient accounts — inline identity). */
  patientName?: string;
  /** Doctor who operated on this visit (stamped on diagnosis submit). */
  assignedDoctor?: string;
  // Verified claim
  claimPurchased?: boolean;
  claimPurchasedAt?: string;
  verificationHash?: string;
  verificationUrl?: string;
  invoice?: {
    invoice_number?: string;
    issued_on?: string;
    line_items?: Array<{
      description: string;
      quantity: number;
      unit_price: number;
    }>;
    subtotal?: number;
    tax_amount?: number;
    total_amount?: number;
    currency?: string;
    notes?: string;
  };
  qrPayload?: string;
}

// Visits ledger is strictly driven by the docked .mtr file or live sessions.
// Zero fallback/dummy records are shown when no .mtr file is docked.

const TABS = [
  { id: "upcoming", label: "Upcoming", icon: FiClock },
  { id: "completed", label: "Completed", icon: FiCheck },
  { id: "cancelled", label: "Cancelled", icon: FiX },
];

const VISITS_SESSION_KEY = "medtour_tab_visits_state";

function VisitsPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: "/visits" });

  const initialTab = useMemo(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem(VISITS_SESSION_KEY);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (parsed.tab) return parsed.tab;
        } catch {}
      }
    }
    return (search as any)?.tab || "upcoming";
  }, []);

  const activeTab = (search as any)?.tab || initialTab;
  const [visits, setVisits] = useState<VisitRecord[]>([]);
  const [isDocked, setIsDocked] = useState<boolean>(false);
  const [selectedCompletedVisit, setSelectedCompletedVisit] = useState<VisitRecord | null>(null);
  const [isMedicalIdOpen, setIsMedicalIdOpen] = useState(false);

  // QR scanner & claim purchase modals
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [claimVisit, setClaimVisit] = useState<VisitRecord | null>(null);
  const [isClaimOpen, setIsClaimOpen] = useState(false);

  // View Session Modal state
  const [sessionModalVisit, setSessionModalVisit] = useState<VisitRecord | null>(null);
  const [isSessionModalOpen, setIsSessionModalOpen] = useState(false);

  // Persist current tab choice into sessionStorage
  useEffect(() => {
    try {
      sessionStorage.setItem(VISITS_SESSION_KEY, JSON.stringify({ tab: activeTab }));
    } catch {}
  }, [activeTab]);

  const loadVisitsLedger = async () => {
    try {
      // 1. Check if a .mtr vault is actually docked or an active medical profile is present
      const mtrDockedFlag = localStorage.getItem("medtour_mtr_docked") === "true";
      const storedMedicalId = localStorage.getItem("medtour_medical_id");
      const hasActiveProfile = !!storedMedicalId && storedMedicalId.includes('"fullName"');

      // Purge any legacy hard-coded demo visits from previous versions
      const stored = localStorage.getItem("medtour_visits");
      if (stored && (stored.includes("Lilavati Hospital") || stored.includes("Apex Care Urgent Clinic") || stored.includes("v-1092") || stored.includes("v-1088"))) {
        localStorage.removeItem("medtour_visits");
      }

      if (!mtrDockedFlag && !hasActiveProfile) {
        setIsDocked(false);
        setVisits([]);
        return;
      }

      setIsDocked(true);

      const refreshedStored = localStorage.getItem("medtour_visits");
      if (refreshedStored) {
        const parsed = JSON.parse(refreshedStored);
        if (Array.isArray(parsed)) {
          setVisits(parsed);
          return;
        }
      }

      // Check device MTR vault
      const { getMtrRecord } = await import("@/lib/mtrDatabase");
      const mtrVisits = await getMtrRecord<VisitRecord[]>("all_visits_ledger");
      if (mtrVisits && mtrVisits.data && Array.isArray(mtrVisits.data)) {
        setVisits(mtrVisits.data);
        localStorage.setItem("medtour_visits", JSON.stringify(mtrVisits.data));
      } else {
        setVisits([]);
      }
    } catch (e) {
      console.warn("Error loading visits ledger:", e);
      setIsDocked(false);
      setVisits([]);
    }
  };

  useEffect(() => {
    loadVisitsLedger();

    const handleDataRestored = () => {
      loadVisitsLedger();
    };

    window.addEventListener("medtour:mtr-restored", handleDataRestored);
    window.addEventListener("medtour:ecs-restored", handleDataRestored);
    return () => {
      window.removeEventListener("medtour:mtr-restored", handleDataRestored);
      window.removeEventListener("medtour:ecs-restored", handleDataRestored);
    };
  }, []);

  const saveVisitsToStorage = (updated: VisitRecord[]) => {
    setVisits(updated);
    try {
      localStorage.setItem("medtour_visits", JSON.stringify(updated));
      // Encrypt and persist to device MTR vault
      import("@/lib/mtrDatabase").then(({ saveMtrRecord }) => {
        saveMtrRecord("all_visits_ledger", "visits", "All Visits Ledger", updated);
      });
      import("@/lib/ecsDatabase").then(({ saveEcsRecord }) => {
        saveEcsRecord("all_visits_ledger", "visits", "All Visits Ledger", updated);
      });
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancelVisit = (id: string) => {
    const updated = visits.map((v) =>
      v.id === id ? { ...v, status: "cancelled" as const, cancellationReason: "Cancelled by user" } : v
    );
    saveVisitsToStorage(updated);
    toast.info("Visit cancelled.");
  };

  const handleDeleteVisit = (id: string) => {
    const updated = visits.filter((v) => v.id !== id);
    saveVisitsToStorage(updated);
    if (selectedCompletedVisit?.id === id) {
      setSelectedCompletedVisit(null);
    }
    toast.success("Visit record removed from local .mtr ledger.");
  };

  /**
   * Called after the patient scans the doctor's QR code.
   * The backend validates the appointment code and returns the full
   * appointment. We convert it into a local VisitRecord and mark it
   * completed so it appears in the Completed tab.
   */
  const handleQrScanSuccess = (appointment: any, clinical?: any) => {
    if (!appointment) return;

    const existingIdx = visits.findIndex(
      (v) => v.appointmentCode === appointment.appointment_code || v.id === `appt-${appointment.id}`,
    );

    const diagnosis = clinical?.diagnosis || appointment.diagnosis;
    const prescription = clinical?.prescription || appointment.prescription;
    const diagnosisNotes = clinical?.notes || appointment.diagnosis_notes;
    const invoice = clinical?.invoice || appointment.invoice;

    let costDisplay = "—";
    if (invoice?.total_amount != null) {
      costDisplay = `${invoice.currency || "USD"} ${invoice.total_amount}`;
    }

    const visitRecord: VisitRecord = {
      id: existingIdx >= 0 ? visits[existingIdx].id : `appt-${appointment.id}`,
      facilityName: appointment.hospital?.name || appointment.hospital_name || "Hospital",
      address: appointment.hospital?.address || "",
      phone: appointment.hospital?.phone || "",
      status: "completed",
      timestamp: appointment.completed_at
        ? new Date(appointment.completed_at).getTime()
        : Date.now(),
      symptoms: appointment.symptoms
        ? [appointment.symptoms]
        : appointment.reason
          ? [appointment.reason]
          : [],
      cost: costDisplay,
      insuranceTaxId: "MEDTOUR-VERIFIED",
      appointmentCode: appointment.appointment_code,
      diagnosis,
      prescription,
      diagnosisNotes,
      completedAt: appointment.completed_at || new Date().toISOString(),
      department: appointment.department,
      claimPurchased: appointment.claim_purchased || false,
      claimPurchasedAt: appointment.claim_purchased_at,
      patientName: appointment.patient_name || getPatientName() || undefined,
      assignedDoctor: appointment.assigned_doctor || appointment.doctor_name || undefined,
      invoice: invoice || undefined,
      qrPayload: clinical?.rawPayload,
    };

    if (existingIdx >= 0) {
      const updated = [...visits];
      updated[existingIdx] = visitRecord;
      saveVisitsToStorage(updated);
    } else {
      saveVisitsToStorage([...visits, visitRecord]);
    }

    // Ensure the ledger is considered docked even if no .mtr was present
    if (!isDocked) {
      setIsDocked(true);
      localStorage.setItem("medtour_mtr_docked", "true");
    }

    // Prompt user to backup their updated .mtr records
    promptMtrBackup("Visit completed — please download your latest .mtr backup before proceeding.");

    // Highlight and view session
    setSelectedCompletedVisit(visitRecord);

    // Switch to the Completed tab so the patient sees the diagnosis
    navigate({ to: "/visits", search: { tab: "completed" } as any });
    toast.success("Visit verified and completed! Details added to your records.");
  };

  const handleAddToNativeCalendar = async (visit: VisitRecord) => {
    try {
      const { downloadIcsFile } = await import("@/lib/calendar");
      downloadIcsFile({
        title: `Hospital Visit: ${visit.facilityName}`,
        description: `Walk-in medical consultation for: ${visit.symptoms.join(", ")}. Reference ID: ${visit.id}`,
        location: visit.address,
        startTime: new Date(visit.timestamp || Date.now() + 1800000),
        durationMinutes: 60,
      }, `visit_${visit.id}.ics`);
      toast.success("Calendar reminder created! Tap file to add to phone calendar.");
    } catch (err) {
      toast.error("Could not generate calendar file.");
    }
  };

  const handleDownloadReceipt = (visit: VisitRecord) => {
    const medicalId = getStoredMedicalId();
    const touristName = medicalId.fullName || "Valued Tourist Guest";
    const passport = medicalId.passportNo || "N/A (Local Guest)";
    const policy = medicalId.insurancePolicyNo || "TRV-GLOBAL-POLICY-01";

    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      toast.error("Pop-up blocked! Allow pop-ups to download PDF receipt.");
      return;
    }

    const htmlContent = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Insurance_Receipt_${visit.id}.pdf</title>
        <style>
          body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 40px; color: #101828; line-height: 1.5; }
          .header { border-bottom: 3px solid #1570EF; padding-bottom: 20px; margin-bottom: 30px; }
          .title { font-size: 24px; font-weight: bold; color: #1570EF; }
          .badge { background: #039855; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; display: inline-block; margin-top: 8px; }
          .section { margin-bottom: 24px; }
          .section-title { font-size: 12px; font-weight: bold; text-transform: uppercase; color: #475467; letter-spacing: 0.5px; border-bottom: 1px solid #EAECF0; padding-bottom: 4px; margin-bottom: 12px; }
          .grid { display: grid; grid-template-cols: 1fr 1fr; gap: 16px; }
          .box { background: #F9FAFB; padding: 12px; border-radius: 8px; border: 1px solid #EAECF0; }
          .label { font-size: 11px; color: #475467; font-weight: bold; }
          .value { font-size: 14px; font-weight: bold; margin-top: 2px; }
          .table { width: 100%; border-collapse: collapse; margin-top: 10px; }
          .table th, .table td { border: 1px solid #EAECF0; padding: 10px; text-align: left; font-size: 13px; }
          .table th { background: #F9FAFB; font-weight: bold; }
          .footer { margin-top: 50px; font-size: 11px; color: #475467; text-align: center; border-top: 1px solid #EAECF0; padding-top: 20px; }
        </style>
      </head>
      <body>
        <div class="header">
          <div class="title">MedTour International Healthcare Claim Receipt</div>
          <p style="margin-top: 4px; font-size: 13px; color: #475467;">Verified Walk-In Urgent Care & Emergency Services Ledger</p>
          <span class="badge">INSURANCE READY • OFFICIAL RECEIPT</span>
        </div>

        <div class="section">
          <div class="section-title">Patient / Tourist Information</div>
          <div class="grid">
            <div class="box"><div class="label">Patient Name</div><div class="value">${touristName}</div></div>
            <div class="box"><div class="label">Passport / ID Number</div><div class="value">${passport}</div></div>
            <div class="box"><div class="label">Insurance Policy No.</div><div class="value">${policy}</div></div>
            <div class="box"><div class="label">Blood Type & Allergies</div><div class="value">${medicalId.bloodType} | ${medicalId.allergies || "None"}</div></div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">Healthcare Facility Details</div>
          <div class="grid">
            <div class="box"><div class="label">Facility Name</div><div class="value">${visit.facilityName}</div></div>
            <div class="box"><div class="label">Facility GSTIN / Tax ID</div><div class="value">${visit.insuranceTaxId}</div></div>
            <div class="box"><div class="label">Address</div><div class="value">${visit.address}</div></div>
            <div class="box"><div class="label">Visit Timestamp</div><div class="value">${new Date(visit.timestamp).toLocaleString()}</div></div>
          </div>
        </div>

        <div class="section">
          <div class="section-title">ICD-10 Clinical Diagnostics Checklist</div>
          <table class="table">
            <thead>
              <tr>
                <th>Symptom / Diagnostic Procedure</th>
                <th>Category</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${visit.symptoms
                .map(
                  (s) => `
                <tr>
                  <td>${s}</td>
                  <td>Urgent Walk-In Triage</td>
                  <td>Verified & Treated</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>

        <div class="section">
          <div class="section-title">Payment Summary</div>
          <div class="box" style="background: #ECFDF5; border-color: #A7F3D0;">
            <div class="label" style="color: #047857;">Total Amount Paid (Local Currency)</div>
            <div class="value" style="font-size: 20px; color: #065F46;">${visit.cost} INR</div>
          </div>
        </div>

        <div class="footer">
          <p>Generated programmatic client-side via MedTour Offline Ledger System. Satisfies global travel insurance verification policies.</p>
        </div>

        <script>
          window.onload = function() { window.print(); }
        </script>
      </body>
      </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
    toast.success("Insurance receipt generated! Opening print/PDF dialog.");
  };

  const upcomingVisits = visits.filter((v) => v.status === "upcoming");
  const completedVisits = visits.filter((v) => v.status === "completed");
  const cancelledVisits = visits.filter((v) => v.status === "cancelled");

  return (
    <div className="min-h-screen bg-background pb-40 font-sans">
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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        {/* Page Header */}
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground tracking-tight">
            My Visits & Insurance Receipts
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Offline 3-tab ledger. Download insurance-ready PDF claim documents instantly.
          </p>
        </div>

        {/* Separated Floating Morphing Pill Tab Switcher directly above bottom navbar */}
        <div className="fixed bottom-[5.75rem] left-0 right-0 z-40 flex justify-center px-3 sm:px-4 pointer-events-none pb-[env(safe-area-inset-bottom)] animate-in fade-in slide-in-from-bottom-3 duration-300">
          <div className="w-fit max-w-[95vw] h-16 flex items-center justify-center gap-1.5 px-2 rounded-full bg-background/90 backdrop-blur-2xl border border-border/80 shadow-[0_12px_36px_rgba(0,0,0,0.18)] pointer-events-auto shrink-0">
            {TABS.map((tab) => {
              const isActive = activeTab === tab.id;
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => navigate({ to: "/visits", search: { tab: tab.id } as any })}
                  className={`relative flex items-center justify-center gap-2 h-12 rounded-full font-extrabold text-sm transition-all duration-300 ${
                    isActive
                      ? "bg-background text-foreground shadow-md px-3 sm:px-4"
                      : "text-muted-foreground/70 hover:text-foreground px-2.5 sm:px-3"
                  }`}
                >
                  {/* Circular Icon Badge */}
                  <div
                    className={`flex items-center justify-center h-10 w-10 shrink-0 rounded-full border-2 transition-all duration-300 ${
                      isActive
                        ? "bg-black text-white dark:bg-white dark:text-black border-black dark:border-white"
                        : "border-black/80 dark:border-white/80 bg-transparent text-foreground"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                  </div>

                  {/* Expanded Label on Active */}
                  {isActive && (
                    <span className="animate-in fade-in slide-in-from-left-2 duration-200 whitespace-nowrap text-sm font-extrabold pr-1">
                      {tab.label}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Prompt banner when no .mtr file is docked */}
        {!isDocked ? (
          <div className="max-w-xl mx-auto py-12 px-4 text-center space-y-4 animate-in fade-in duration-300">
            <div className="h-16 w-16 rounded-full bg-amber-500/15 border-2 border-amber-500/30 text-amber-500 flex items-center justify-center mx-auto text-2xl font-bold shadow-lg">
              <FiShield className="h-8 w-8" />
            </div>
            <div className="space-y-1.5">
              <h3 className="text-xl font-black text-foreground">No .MTR Vault Docked</h3>
              <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
                Your medical visits and insurance claims ledger are only visible when a verified <code className="font-bold text-foreground">.mtr</code> database file is decrypted and docked into this browser.
              </p>
            </div>
            <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button
                onClick={() => setIsMedicalIdOpen(true)}
                className="h-11 px-6 rounded-2xl bg-amber-500 hover:bg-amber-600 text-white font-extrabold text-sm shadow-md"
              >
                Dock / Import .mtr File
              </Button>
              <Button
                onClick={() => navigate({ to: "/walk-in" })}
                variant="outline"
                className="h-11 px-6 rounded-2xl font-bold text-sm"
              >
                Browse Walk-In Clinics
              </Button>
            </div>
          </div>
        ) : (
          /* Desktop Split Layout for Completed Tab Inline PDF Preview */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className={`${activeTab === "completed" ? "lg:col-span-6" : "lg:col-span-12"} space-y-4`}>
              {/* Tab 1: UPCOMING */}
              {activeTab === "upcoming" && (
                <div className="space-y-4">
                  {upcomingVisits.length === 0 ? (
                    <Card className="p-8 text-center rounded-2xl border-dashed">
                      <p className="text-sm font-semibold text-muted-foreground">No upcoming visits in docked ledger.</p>
                      <Button onClick={() => navigate({ to: "/walk-in" })} className="mt-3 text-xs font-bold rounded-xl bg-primary">
                        Find a Clinic
                      </Button>
                    </Card>
                  ) : (
                  upcomingVisits.map((visit) => (
                    <Card key={visit.id} className="rounded-2xl border-2 border-primary/40 bg-card p-5 space-y-4 shadow-sm">
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold inline-block mb-2">
                            Arrival Countdown Active
                          </span>
                          <h3 className="text-lg font-bold text-foreground">{visit.facilityName}</h3>
                          <p className="text-xs text-muted-foreground mt-0.5">{visit.address}</p>
                        </div>
                        <div className="text-right">
                          <span className="text-xs font-bold text-muted-foreground block">Est. Queue Wait</span>
                          <span className="text-lg font-extrabold text-emerald-600 dark:text-emerald-400">~15 Mins</span>
                        </div>
                      </div>

                      <div className="p-3 rounded-xl bg-muted/30 border border-border/60 text-xs">
                        <span className="font-bold text-foreground block">Reported Symptoms / Need:</span>
                        <span className="text-muted-foreground">{visit.symptoms.join(", ")}</span>
                      </div>

                      <div className="flex flex-col sm:flex-row gap-2 pt-1">
                        <Button
                          onClick={() => handleAddToNativeCalendar(visit)}
                          variant="outline"
                          className="h-10 rounded-xl border-primary/30 text-primary hover:bg-primary/10 font-bold text-xs flex items-center justify-center gap-1.5"
                        >
                          📅 Add to Phone Calendar
                        </Button>
                        <Button
                          onClick={() => setIsScannerOpen(true)}
                          className="flex-1 h-10 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs shadow-xs flex items-center justify-center gap-1.5"
                        >
                          <FiCamera className="h-4 w-4 shrink-0" />
                          Scan Doctor QR Code
                        </Button>
                        <Button
                          onClick={() => handleCancelVisit(visit.id)}
                          variant="outline"
                          className="h-10 rounded-xl border-red-500/30 text-red-600 hover:bg-red-500/10 font-bold text-xs"
                        >
                          Cancel Visit
                        </Button>
                      </div>
                    </Card>
                  ))
                )}
              </div>
            )}

            {/* Tab 2: COMPLETED */}
            {activeTab === "completed" && (
              <div className="space-y-4">
                {completedVisits.length === 0 ? (
                  <Card className="p-8 text-center rounded-2xl border-dashed">
                    <p className="text-sm font-semibold text-muted-foreground">No completed visits recorded yet.</p>
                  </Card>
                ) : (
                  completedVisits.map((visit) => {
                    const isSelected = selectedCompletedVisit?.id === visit.id;
                    const hasDiagnosis = !!(visit.diagnosis && visit.appointmentCode);
                    return (
                      <Card
                        key={visit.id}
                        onClick={() => setSelectedCompletedVisit(visit)}
                        className={`rounded-2xl border-2 transition-all cursor-pointer p-4 space-y-3 ${
                          isSelected
                            ? "border-emerald-500 bg-emerald-500/5 shadow-md"
                            : "border-border/70 bg-card hover:border-border hover:shadow-xs"
                        }`}
                      >
                        {/* Header & Badges */}
                        <div className="flex justify-between items-start gap-2">
                          <div className="space-y-1 min-w-0 flex-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 text-[11px] font-bold inline-block">
                                ✓ Completed
                              </span>
                              {visit.claimPurchased ? (
                                <span className="px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 border border-blue-500/30 text-[10px] font-extrabold inline-flex items-center gap-1">
                                  <FiShield className="h-3 w-3" /> Verified
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 border border-amber-500/30 text-[10px] font-bold">
                                  Claim Ready
                                </span>
                              )}
                              {visit.appointmentCode && (
                                <span className="text-[10px] font-mono font-bold text-foreground bg-muted px-2 py-0.5 rounded-md border border-border/80">
                                  {visit.appointmentCode}
                                </span>
                              )}
                            </div>
                            <h3 className="text-base font-extrabold text-foreground truncate">
                              {visit.facilityName}
                            </h3>
                            <p className="text-xs text-muted-foreground truncate">
                              {visit.department || "General Medicine"}
                              {visit.assignedDoctor ? ` • Dr. ${visit.assignedDoctor}` : ""}
                              {" • "}
                              {new Date(visit.timestamp).toLocaleDateString()}
                            </p>
                          </div>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (window.confirm(`Delete visit at ${visit.facilityName} from your .mtr vault?`)) {
                                handleDeleteVisit(visit.id);
                              }
                            }}
                            className="h-8 w-8 rounded-lg flex items-center justify-center text-muted-foreground/60 hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0 cursor-pointer"
                            title="Delete this visit from your .mtr records"
                          >
                            <FiTrash2 className="h-4 w-4" />
                          </button>
                        </div>

                        {/* Minimal Sub-Summary: Patient + Cost */}
                        <div className="flex items-center justify-between text-xs px-3 py-2 rounded-xl bg-muted/30 border border-border/50">
                          <span className="text-muted-foreground truncate">
                            <strong>Patient:</strong> {visit.patientName || getPatientName() || "Guest"}
                          </span>
                          {visit.invoice?.total_amount != null && (
                            <span className="font-mono font-bold text-emerald-600 dark:text-emerald-400 shrink-0 ml-2">
                              {visit.invoice.currency || "USD"} {Number(visit.invoice.total_amount).toFixed(2)}
                            </span>
                          )}
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2 pt-0.5">
                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSessionModalVisit(visit);
                              setIsSessionModalOpen(true);
                            }}
                            variant="outline"
                            className="flex-1 h-9 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5 hover:bg-muted/60"
                          >
                            <FiEye className="h-3.5 w-3.5" /> View Session
                          </Button>

                          <Button
                            onClick={(e) => {
                              e.stopPropagation();
                              setClaimVisit(visit);
                              setIsClaimOpen(true);
                            }}
                            className={`flex-1 h-9 rounded-xl font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-xs ${
                              visit.claimPurchased
                                ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                                : "bg-black text-white dark:bg-white dark:text-black hover:opacity-90"
                            }`}
                          >
                            {visit.claimPurchased ? (
                              <>
                                <FiDownload className="h-3.5 w-3.5 shrink-0" />
                                <span className="truncate">Download PDF</span>
                              </>
                            ) : (
                              <>
                                <FiShield className="h-3.5 w-3.5 shrink-0" />
                                <span className="truncate">Mediclaim ($15)</span>
                              </>
                            )}
                          </Button>
                        </div>
                      </Card>
                    );
                  })
                )}
              </div>
            )}

            {/* Tab 3: CANCELLED */}
            {activeTab === "cancelled" && (
              <div className="space-y-4">
                {cancelledVisits.length === 0 ? (
                  <Card className="p-8 text-center rounded-2xl border-dashed">
                    <p className="text-sm font-semibold text-muted-foreground">No cancelled visits.</p>
                  </Card>
                ) : (
                  cancelledVisits.map((visit) => (
                    <Card key={visit.id} className="rounded-2xl border border-border bg-muted/20 p-5 space-y-3">
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="px-2.5 py-0.5 rounded-full bg-gray-500/10 text-gray-500 text-xs font-bold inline-block mb-1.5">
                            Cancelled
                          </span>
                          <h3 className="text-base font-bold text-foreground">{visit.facilityName}</h3>
                          <p className="text-xs text-muted-foreground">{visit.address}</p>
                        </div>
                      </div>
                      <Button
                        onClick={() => navigate({ to: "/walk-in" })}
                        variant="outline"
                        className="w-full h-10 rounded-xl font-bold text-xs border-border"
                      >
                        Re-book Walk-in
                      </Button>
                    </Card>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Desktop Right Side PDF Preview Pane for Completed Visits */}
          {activeTab === "completed" && (
            <div className="hidden lg:block lg:col-span-6 sticky top-20">
              <Card className="rounded-3xl border-border/80 overflow-hidden shadow-md bg-card p-6 space-y-4">
                <div className="flex items-center justify-between border-b border-border pb-3">
                  <div className="flex items-center gap-2">
                    <FiShield className="h-5 w-5 text-emerald-600" />
                    <h3 className="text-base font-bold text-foreground">Inline Claim PDF Preview</h3>
                  </div>
                  <span className="text-xs font-bold text-muted-foreground uppercase">Insurer Verification Format</span>
                </div>

                {selectedCompletedVisit ? (
                  <div className="p-5 rounded-2xl bg-muted/20 border border-border space-y-4 text-xs font-sans">
                    <div className="border-b border-border/60 pb-3">
                      <span className="text-[10px] font-bold uppercase text-primary tracking-wider block">
                        {selectedCompletedVisit.appointmentCode ? "Verified Mediclaim" : "Official Receipt"}
                      </span>
                      <h4 className="text-lg font-black text-foreground">{selectedCompletedVisit.facilityName}</h4>
                      <p className="text-muted-foreground">{selectedCompletedVisit.insuranceTaxId}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <span className="font-bold text-muted-foreground block">Patient Name</span>
                        <span className="font-extrabold text-foreground">{getStoredMedicalId().fullName || "Local Guest"}</span>
                      </div>
                      <div>
                        <span className="font-bold text-muted-foreground block">Passport / ID</span>
                        <span className="font-extrabold text-foreground">{getStoredMedicalId().passportNo || "N/A"}</span>
                      </div>
                    </div>

                    {selectedCompletedVisit.diagnosis && (
                      <div className="rounded-xl bg-muted/30 border border-border/60 p-3 space-y-1.5">
                        <span className="font-bold text-foreground block">🩺 Diagnosis</span>
                        <p className="text-muted-foreground">{selectedCompletedVisit.diagnosis}</p>
                        {selectedCompletedVisit.prescription && (
                          <>
                            <span className="font-bold text-foreground block pt-1">💊 Prescription</span>
                            <p className="text-muted-foreground">{selectedCompletedVisit.prescription}</p>
                          </>
                        )}
                      </div>
                    )}

                    {/* Invoice */}
                    {selectedCompletedVisit.invoice && (
                      <div className="rounded-xl bg-muted/20 border border-border/60 p-3 space-y-1.5">
                        <div className="flex justify-between items-center font-bold text-foreground">
                          <span>Invoice #{selectedCompletedVisit.invoice.invoice_number || "MT-INV"}</span>
                          <span className="font-mono text-emerald-600">
                            {selectedCompletedVisit.invoice.currency || "USD"}{" "}
                            {selectedCompletedVisit.invoice.total_amount ?? 0}
                          </span>
                        </div>
                        {Array.isArray(selectedCompletedVisit.invoice.line_items) && (
                          <div className="space-y-0.5 pt-1 text-[11px] text-muted-foreground border-t border-border/40">
                            {selectedCompletedVisit.invoice.line_items.map((li, idx) => (
                              <div key={idx} className="flex justify-between">
                                <span>{li.description}</span>
                                <span className="font-mono">
                                  {selectedCompletedVisit.invoice?.currency || "USD"}{" "}
                                  {(li.quantity * li.unit_price).toFixed(2)}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex justify-between items-center">
                      <div>
                        <span className="text-[10px] font-bold text-muted-foreground uppercase block">
                          Total Bill
                        </span>
                        <span className="text-xl font-black text-emerald-700">
                          {selectedCompletedVisit.cost}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] font-bold text-muted-foreground uppercase block">
                          Report Fee
                        </span>
                        <span className="text-sm font-bold text-emerald-700">$15 USD</span>
                      </div>
                    </div>

                    <div className="flex gap-2 pt-1">
                      <Button
                        onClick={() => {
                          setSessionModalVisit(selectedCompletedVisit);
                          setIsSessionModalOpen(true);
                        }}
                        variant="outline"
                        className="flex-1 h-11 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5"
                      >
                        <FiEye className="h-4 w-4" /> View Full Session
                      </Button>

                      <Button
                        onClick={() => {
                          setClaimVisit(selectedCompletedVisit);
                          setIsClaimOpen(true);
                        }}
                        className={`flex-1 h-11 rounded-xl font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-xs ${
                          selectedCompletedVisit.claimPurchased
                            ? "bg-emerald-600 text-white hover:bg-emerald-700"
                            : "bg-amber-500 text-white hover:bg-amber-600"
                        }`}
                      >
                        {selectedCompletedVisit.claimPurchased ? (
                          <>
                            <FiDownload className="h-4 w-4" />
                            Download Mediclaim
                          </>
                        ) : (
                          <>
                            <FiShield className="h-4 w-4" />
                            Generate Report ($15)
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="p-12 text-center text-muted-foreground text-xs italic">
                    Select a completed visit from the left pane to view its claim receipt preview.
                  </div>
                )}
              </Card>
            </div>
          )}
        </div>
        )}
      </main>

      <MobileNav onOpenMedicalId={() => setIsMedicalIdOpen(true)} />
      <QuickMedicalIdModal isOpen={isMedicalIdOpen} onClose={() => setIsMedicalIdOpen(false)} />

      {/* Doctor QR Scanner */}
      <QrScannerModal
        isOpen={isScannerOpen}
        onClose={() => setIsScannerOpen(false)}
        onScanSuccess={handleQrScanSuccess}
      />

      {/* Verified Claim Purchase / Download */}
      <ClaimPurchaseModal
        isOpen={isClaimOpen}
        onClose={() => setIsClaimOpen(false)}
        visit={claimVisit}
        onSuccess={() => {
          loadVisitsLedger();
        }}
      />

      {/* Full Session Documentation Modal */}
      {sessionModalVisit && (
        <Dialog open={isSessionModalOpen} onOpenChange={setIsSessionModalOpen}>
          <DialogContent className="rounded-3xl max-w-lg p-0 gap-0 overflow-hidden max-h-[90vh] flex flex-col">
            <DialogHeader className="px-6 pt-5 pb-3 border-b border-border shrink-0">
              <DialogTitle className="text-base font-bold flex items-center gap-2">
                <FiFileText className="h-4 w-4 text-primary" />
                Session Documentation — {sessionModalVisit.appointmentCode || sessionModalVisit.id}
              </DialogTitle>
            </DialogHeader>

            <div className="p-6 space-y-4 overflow-y-auto">
              {/* Patient Details */}
              <div className="p-4 rounded-2xl bg-muted/30 border border-border/70 space-y-2 text-xs">
                <h4 className="font-extrabold text-foreground uppercase tracking-wider text-[11px] text-primary">
                  Patient & Facility Details
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <span className="text-muted-foreground font-semibold block">Patient</span>
                    <span className="font-bold text-foreground">
                      {sessionModalVisit.patientName || getPatientName() || "Valued Tourist Guest"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-semibold block">Facility</span>
                    <span className="font-bold text-foreground">{sessionModalVisit.facilityName}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-semibold block">Doctor</span>
                    <span className="font-bold text-foreground">
                      {sessionModalVisit.assignedDoctor ? `Dr. ${sessionModalVisit.assignedDoctor}` : "Attending Physician"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-semibold block">Department</span>
                    <span className="font-bold text-foreground">{sessionModalVisit.department || "General Medicine"}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-semibold block">Visit Time</span>
                    <span className="font-bold text-foreground">{new Date(sessionModalVisit.timestamp).toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground font-semibold block">Reason</span>
                    <span className="font-bold text-foreground">{sessionModalVisit.symptoms?.join(", ") || "Walk-In"}</span>
                  </div>
                </div>
              </div>

              {/* Clinical Section */}
              <div className="p-4 rounded-2xl bg-muted/30 border border-border/70 space-y-2.5 text-xs">
                <h4 className="font-extrabold text-foreground uppercase tracking-wider text-[11px] text-primary">
                  Clinical Record
                </h4>
                <div>
                  <span className="font-bold text-foreground block">🩺 Diagnosis</span>
                  <p className="text-muted-foreground mt-0.5">{sessionModalVisit.diagnosis || "No diagnosis recorded."}</p>
                </div>
                {sessionModalVisit.prescription && (
                  <div className="pt-2 border-t border-border/40">
                    <span className="font-bold text-foreground block">💊 Prescription</span>
                    <p className="text-muted-foreground mt-0.5">{sessionModalVisit.prescription}</p>
                  </div>
                )}
                {sessionModalVisit.diagnosisNotes && (
                  <div className="pt-2 border-t border-border/40">
                    <span className="font-bold text-foreground block">Clinical Notes</span>
                    <p className="text-muted-foreground mt-0.5">{sessionModalVisit.diagnosisNotes}</p>
                  </div>
                )}
              </div>

              {/* Invoice Section */}
              {sessionModalVisit.invoice ? (
                <div className="p-4 rounded-2xl bg-muted/30 border border-border/70 space-y-2 text-xs">
                  <div className="flex justify-between items-center border-b border-border/40 pb-2">
                    <h4 className="font-extrabold text-foreground uppercase tracking-wider text-[11px] text-emerald-600">
                      Doctor Invoice ({sessionModalVisit.invoice.invoice_number || "Bill"})
                    </h4>
                    <span className="font-mono font-bold text-emerald-600 text-sm">
                      {sessionModalVisit.invoice.currency || "USD"} {sessionModalVisit.invoice.total_amount ?? 0}
                    </span>
                  </div>
                  {Array.isArray(sessionModalVisit.invoice.line_items) && (
                    <div className="space-y-1.5 pt-1">
                      {sessionModalVisit.invoice.line_items.map((li, idx) => (
                        <div key={idx} className="flex justify-between text-muted-foreground">
                          <span>{li.description} (x{li.quantity})</span>
                          <span className="font-mono font-semibold text-foreground">
                            {sessionModalVisit.invoice?.currency || "USD"}{" "}
                            {(li.quantity * li.unit_price).toFixed(2)}
                          </span>
                        </div>
                      ))}
                      {sessionModalVisit.invoice.tax_amount ? (
                        <div className="flex justify-between text-muted-foreground pt-1 border-t border-border/30">
                          <span>Tax Amount</span>
                          <span className="font-mono font-semibold text-foreground">
                            {sessionModalVisit.invoice.currency || "USD"} {sessionModalVisit.invoice.tax_amount}
                          </span>
                        </div>
                      ) : null}
                    </div>
                  )}
                </div>
              ) : null}

            </div>

            <div className="p-4 border-t border-border bg-card/80 shrink-0 flex gap-2">
              <Button
                onClick={() => {
                  setIsSessionModalOpen(false);
                  setClaimVisit(sessionModalVisit);
                  setIsClaimOpen(true);
                }}
                className="flex-1 h-11 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs"
              >
                {sessionModalVisit.claimPurchased ? "Download Verified Mediclaim" : "Generate Mediclaim ($15)"}
              </Button>
              <Button
                onClick={() => setIsSessionModalOpen(false)}
                variant="outline"
                className="h-11 px-5 rounded-2xl font-bold text-xs"
              >
                Close
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
