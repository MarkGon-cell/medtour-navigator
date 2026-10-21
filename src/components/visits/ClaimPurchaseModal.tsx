import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FiCreditCard, FiShield, FiDownload, FiLock, FiCheck, FiRefreshCw, FiExternalLink } from "react-icons/fi";
import { toast } from "sonner";
import api from "@/lib/api";
import { getStoredMedicalId } from "@/components/site/QuickMedicalIdModal";

interface ClaimPurchaseModalProps {
  isOpen: boolean;
  onClose: () => void;
  visit: {
    id: string;
    facilityName: string;
    address: string;
    appointmentCode?: string;
    diagnosis?: string;
    prescription?: string;
    diagnosisNotes?: string;
    completedAt?: string;
    appointmentTime?: string;
    department?: string;
    patientName?: string;
    symptoms?: string[] | string;
    assignedDoctor?: string;
    claimPurchased?: boolean;
    invoice?: any;
    verificationUrl?: string;
  } | null;
  onSuccess?: () => void;
}

const REPORT_FEE_LABEL = "$15 USD";

/** Convert Base64 data to Blob */
function base64ToBlob(base64: string, contentType = "application/pdf"): Blob {
  const cleanBase64 = base64.replace(/^data:application\/pdf;base64,/, "").trim();
  const byteCharacters = atob(cleanBase64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: contentType });
}

export function ClaimPurchaseModal({ isOpen, onClose, visit, onSuccess }: ClaimPurchaseModalProps) {
  const [step, setStep] = useState<"pay" | "password" | "generating" | "done">("pay");
  const [mtrPassword, setMtrPassword] = useState("");
  const [claimPurchased, setClaimPurchased] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [verificationUrl, setVerificationUrl] = useState<string | null>(null);
  const [claimResponse, setClaimResponse] = useState<any>(null);

  useEffect(() => {
    if (isOpen && visit) {
      if (visit.claimPurchased) {
        setStep("password");
        setClaimPurchased(true);
      } else {
        setStep("pay");
        setClaimPurchased(false);
      }
    }
  }, [isOpen, visit]);

  if (!visit) return null;

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      onClose();
      setTimeout(() => {
        setStep("pay");
        setMtrPassword("");
        setClaimPurchased(false);
        setProcessing(false);
        setDownloadUrl(null);
        setVerificationUrl(null);
        setClaimResponse(null);
      }, 300);
    }
  };

  /** Prepare patient profile block from local medical ID */
  const buildPatientProfile = () => {
    try {
      const medId = getStoredMedicalId();
      return {
        full_name: medId.fullName || visit.patientName || undefined,
        passport_no: medId.passportNo || undefined,
        national_id_no: medId.nationalIdNo || undefined,
        date_of_birth: medId.dateOfBirth || undefined,
        nationality: medId.nationality || undefined,
        gender: medId.gender || undefined,
        blood_type: medId.bloodType || undefined,
        allergies: medId.allergies || undefined,
        conditions: medId.conditions || undefined,
        medications: medId.medications || undefined,
        insurance_policy_no: medId.insurancePolicyNo || undefined,
        insurance_provider: medId.insuranceProvider || undefined,
        emergency_contact_name: medId.emergencyContactName || undefined,
        emergency_contact_phone: medId.emergencyContactPhone || undefined,
      };
    } catch {
      return undefined;
    }
  };

  /** Retrieve invoice from clinical cache or visit record */
  const getInvoiceData = () => {
    if (visit.invoice) return visit.invoice;
    if (visit.appointmentCode) {
      try {
        const raw = localStorage.getItem(`medtour_doctor_clinical:${visit.appointmentCode}`);
        if (raw) {
          const parsed = JSON.parse(raw);
          if (parsed?.invoice) return parsed.invoice;
        }
      } catch {}
    }
    return undefined;
  };

  const savePdfToVault = async (pdfBase64: string, resData: any) => {
    try {
      const { saveMtrRecord } = await import("@/lib/mtrDatabase");
      await saveMtrRecord(
        `claim-${visit.appointmentCode || visit.id}`,
        "document",
        `Verified Mediclaim — ${visit.facilityName}`,
        {
          appointmentCode: visit.appointmentCode,
          hospitalName: resData.hospital_name || visit.facilityName,
          diagnosis: resData.diagnosis || visit.diagnosis,
          prescription: resData.prescription || visit.prescription,
          doctorName: resData.doctor_name || visit.assignedDoctor,
          doctorRegNumber: resData.doctor_reg_number,
          doctorVerified: resData.doctor_verified,
          isVerified: true,
          invoiceNumber: resData.invoice_number,
          amount: resData.amount,
          currency: resData.currency,
          reportFee: resData.report_fee,
          verificationUrl: resData.verification_url,
          pdfBase64,
          generatedAt: new Date().toISOString(),
        },
      );
    } catch (vaultErr) {
      console.warn("[Claim] Vault save failed:", vaultErr);
    }
  };

  const handlePayAndGenerate = async () => {
    if (!visit.appointmentCode) {
      toast.error("No appointment code found for this visit.");
      return;
    }
    if (!mtrPassword || mtrPassword.trim().length < 4) {
      toast.error("Please enter a valid password (min 4 characters).");
      return;
    }

    setProcessing(true);
    setStep("generating");
    try {
      const patient = buildPatientProfile();
      const invoice = getInvoiceData();

      const payload: any = {
        appointment_code: visit.appointmentCode,
        diagnosis: visit.diagnosis || undefined,
        prescription: visit.prescription || undefined,
        diagnosis_notes: visit.diagnosisNotes || undefined,
        invoice: invoice || undefined,
        patient: patient || undefined,
        mtr_password: mtrPassword.trim(),
      };

      // Call backend claim endpoint
      // If visit.claimPurchased is already true, call /doctor/claim/pdf, else /doctor/claim/purchase
      const endpoint = visit.claimPurchased ? "/doctor/claim/pdf" : "/doctor/claim/purchase";
      const res = await api.post(endpoint, payload);
      const resData = res.data;

      setClaimPurchased(true);
      setClaimResponse(resData);
      setVerificationUrl(resData.verification_url || null);

      if (resData.pdf_base64) {
        // Create Blob and Object URL
        const blob = base64ToBlob(resData.pdf_base64, "application/pdf");
        const url = URL.createObjectURL(blob);
        setDownloadUrl(url);

        // Auto trigger download
        const a = document.createElement("a");
        a.href = url;
        a.download = `Verified_Mediclaim_${visit.appointmentCode}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        // Save PDF to medtour vault
        await savePdfToVault(resData.pdf_base64, resData);
      }

      // Update visit in localStorage
      try {
        const rawVisits = localStorage.getItem("medtour_visits");
        if (rawVisits) {
          const list = JSON.parse(rawVisits);
          if (Array.isArray(list)) {
            const updated = list.map((v: any) =>
              v.appointmentCode === visit.appointmentCode || v.id === visit.id
                ? {
                    ...v,
                    claimPurchased: true,
                    claimPurchasedAt: resData.claim_purchased_at || new Date().toISOString(),
                    verificationUrl: resData.verification_url,
                  }
                : v,
            );
            localStorage.setItem("medtour_visits", JSON.stringify(updated));
          }
        }
      } catch {}

      if (onSuccess) onSuccess();

      setStep("done");
      toast.success(
        visit.claimPurchased
          ? "Mediclaim PDF regenerated and downloaded successfully!"
          : "Payment successful! Verified Mediclaim PDF unlocked and downloaded.",
      );
    } catch (err: any) {
      console.error("[Claim] PDF generation failed:", err);
      const msg = err?.response?.data?.detail || "Failed to process mediclaim report.";
      toast.error(msg);
      setStep(visit.claimPurchased ? "password" : "pay");
    } finally {
      setProcessing(false);
    }
  };

  const handleReDownload = () => {
    if (downloadUrl) {
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `Verified_Mediclaim_${visit.appointmentCode}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      toast.success("Download started.");
    } else {
      setStep("password");
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogContent className="rounded-2xl max-w-md p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-border">
          <DialogTitle className="text-base font-bold flex items-center gap-2">
            <FiShield className="h-4 w-4 text-emerald-600" />
            Verified Mediclaim Document
          </DialogTitle>
        </DialogHeader>

        <div className="p-5 space-y-4">
          {/* Visit summary */}
          <div className="rounded-xl bg-muted/30 border border-border/60 p-3 space-y-1 text-xs">
            <p className="font-bold text-foreground">{visit.facilityName}</p>
            <p className="text-muted-foreground">{visit.address}</p>
            {visit.appointmentCode && (
              <p className="font-mono font-bold text-primary">
                Code: {visit.appointmentCode}
              </p>
            )}
          </div>

          {/* Step 1: Payment or Password prompt */}
          {step === "pay" && (
            <>
              <div className="rounded-xl border-2 border-emerald-500/30 bg-emerald-500/5 p-4 space-y-2 text-center">
                <FiCreditCard className="h-8 w-8 text-emerald-600 mx-auto" />
                <p className="text-2xl font-black text-emerald-700 dark:text-emerald-400">
                  {REPORT_FEE_LABEL}
                </p>
                <p className="text-xs text-muted-foreground">
                  One-time fee to generate the official, password-protected
                  verified mediclaim report with line-item bill & verification QR.
                  Re-downloads are free.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="mtr-pass" className="text-xs font-bold">
                  .mtr Master Password (to encrypt PDF)
                </Label>
                <Input
                  id="mtr-pass"
                  type="password"
                  placeholder="Enter your .mtr passphrase"
                  value={mtrPassword}
                  onChange={(e) => setMtrPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handlePayAndGenerate()}
                  className="rounded-xl text-sm h-11"
                />
                <p className="text-[11px] text-muted-foreground">
                  The PDF will be securely encrypted with this passphrase before downloading.
                </p>
              </div>

              <Button
                onClick={handlePayAndGenerate}
                disabled={processing || mtrPassword.trim().length < 4}
                className="w-full h-12 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-sm"
              >
                {processing ? "Processing…" : `Pay ${REPORT_FEE_LABEL} & Download PDF`}
              </Button>
            </>
          )}

          {/* Step 2: Password prompt (for free re-download) */}
          {step === "password" && (
            <>
              <div className="rounded-xl border-2 border-primary/30 bg-primary/5 p-4 space-y-2 text-center">
                <FiLock className="h-8 w-8 text-primary mx-auto" />
                <p className="text-sm font-bold text-foreground">
                  Re-generate Verified Mediclaim PDF (Free)
                </p>
                <p className="text-xs text-muted-foreground">
                  Already paid! Enter your <strong>.mtr password</strong> to decrypt and
                  re-generate your verified mediclaim document.
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="mtr-pass-regen" className="text-xs font-bold">
                  .mtr Master Password
                </Label>
                <Input
                  id="mtr-pass-regen"
                  type="password"
                  placeholder="Enter your .mtr password"
                  value={mtrPassword}
                  onChange={(e) => setMtrPassword(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handlePayAndGenerate()}
                  className="rounded-xl text-sm h-11"
                />
              </div>

              <Button
                onClick={handlePayAndGenerate}
                disabled={processing || mtrPassword.trim().length < 4}
                className="w-full h-12 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-sm"
              >
                {processing ? "Generating…" : "Generate & Download PDF"}
              </Button>
            </>
          )}

          {/* Step 3: Generating */}
          {step === "generating" && (
            <div className="py-8 text-center space-y-3">
              <div className="h-12 w-12 rounded-full border-4 border-primary border-t-transparent animate-spin mx-auto" />
              <p className="text-sm font-bold text-foreground">
                Generating verified PDF on server…
              </p>
              <p className="text-xs text-muted-foreground">
                Rendering line items, doctor credentials, and cryptographic QR.
              </p>
            </div>
          )}

          {/* Step 4: Done */}
          {step === "done" && (
            <>
              <div className="rounded-xl border-2 border-emerald-500/40 bg-emerald-500/5 p-5 text-center space-y-2">
                <FiCheck className="h-10 w-10 text-emerald-600 mx-auto" />
                <p className="text-base font-bold text-emerald-700 dark:text-emerald-400">
                  PDF Generated & Downloaded!
                </p>
                <p className="text-xs text-muted-foreground">
                  The password-protected verified mediclaim PDF has been downloaded
                  and safely stored in your encrypted .mtr vault.
                </p>
                {verificationUrl && (
                  <p className="text-[11px] text-muted-foreground pt-1">
                    Public Verification Link:{" "}
                    <a
                      href={verificationUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary font-semibold underline inline-flex items-center gap-1"
                    >
                      Verify Claim <FiExternalLink className="h-3 w-3" />
                    </a>
                  </p>
                )}
              </div>

              <div className="flex gap-2">
                <Button
                  onClick={handleReDownload}
                  variant="outline"
                  className="flex-1 h-11 rounded-xl font-bold text-xs flex items-center justify-center gap-1.5"
                >
                  <FiDownload className="h-4 w-4" /> Download Again
                </Button>
                <Button
                  onClick={onClose}
                  className="flex-1 h-11 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-sm"
                >
                  Done
                </Button>
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
