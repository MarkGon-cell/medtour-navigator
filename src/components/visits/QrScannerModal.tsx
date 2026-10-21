import { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FiCamera, FiX, FiKey } from "react-icons/fi";
import { toast } from "sonner";
import api from "@/lib/api";

interface QrScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  /**
   * `appointment` is the server's status-only row; `clinical` is whatever
   * diagnosis/prescription rode inside the scanned payload. They are passed
   * separately because only the first one exists on the server.
   */
  onScanSuccess: (appointment: any, clinical: ScannedClinical) => void;
}

import { gcm } from "@noble/ciphers/aes.js";
import { sha256 } from "@noble/hashes/sha2.js";
import { base64ToUint8 } from "@/lib/cryptoEngine";

/** Clinical detail & bill recovered from the QR payload — never fetched from the DB. */
export interface ScannedClinical {
  diagnosis?: string;
  prescription?: string;
  notes?: string;
  invoice?: any;
  rawPayload?: string;
}

/** Pull the clinical trio and bill out of a scanned payload, decrypting if encrypted with aID. */
function extractClinical(raw: string): ScannedClinical {
  try {
    let parsed = JSON.parse(raw);

    // If payload was encrypted with aID (appointment code)
    if (parsed && typeof parsed === "object" && parsed.encrypted && parsed.iv && parsed.data) {
      try {
        const aid = (parsed.code || "").trim();
        if (aid) {
          const enc = new TextEncoder();
          const key = sha256(enc.encode(aid));
          const iv = base64ToUint8(parsed.iv);
          const ciphertext = base64ToUint8(parsed.data);
          const cipher = gcm(key, iv);
          const plaintextBytes = cipher.decrypt(ciphertext);
          const decodedJson = new TextDecoder().decode(plaintextBytes);
          parsed = JSON.parse(decodedJson);
        }
      } catch (decErr) {
        console.warn("[QrScanner] Failed to decrypt encrypted payload with aID:", decErr);
      }
    }

    if (parsed && typeof parsed === "object") {
      return {
        diagnosis: typeof parsed.dx === "string" ? parsed.dx : undefined,
        prescription: typeof parsed.rx === "string" ? parsed.rx : undefined,
        notes: typeof parsed.notes === "string" ? parsed.notes : undefined,
        invoice: parsed.bill || undefined,
        rawPayload: raw,
      };
    }
  } catch {
    // Not JSON — the payload was a plain appointment code typed by hand.
  }
  return { rawPayload: raw };
}

/**
 * QR Scanner Modal — patient scans the doctor's QR code.
 * Uses html5-qrcode for camera scanning + a manual code-entry fallback.
 * On success the backend validates the appointment code and returns
 * the full appointment so the caller can auto-enter it into the ledger.
 */
export function QrScannerModal({ isOpen, onClose, onScanSuccess }: QrScannerModalProps) {
  const videoRef = useRef<HTMLDivElement>(null);
  const scannerRef = useRef<any>(null);
  const [scanning, setScanning] = useState(false);
  const [manualCode, setManualCode] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [mode, setMode] = useState<"camera" | "manual">("manual");
  // Why the last scan was refused (id mismatch, no diagnosis, unknown code).
  const [errorNotes, setErrorNotes] = useState<string | null>(null);

  // Cleanup scanner on close/unmount
  useEffect(() => {
    return () => {
      stopScanner();
    };
  }, []);

  useEffect(() => {
    if (!isOpen) {
      stopScanner();
      setMode("manual");
      setErrorNotes(null);
    }
  }, [isOpen]);

  // Start the camera once the viewport actually exists in the DOM. The
  // reader div only renders in camera mode, so the switch to "camera" and
  // the start() call must be split across a render — otherwise `videoRef`
  // is still null and startScanner() silently returns, leaving the button
  // looking dead and never triggering the browser's permission prompt.
  useEffect(() => {
    if (isOpen && mode === "camera" && !scannerRef.current) {
      startScanner();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, mode]);

  const stopScanner = async () => {
    if (scannerRef.current) {
      try {
        await scannerRef.current.stop();
        scannerRef.current.clear();
      } catch {}
      scannerRef.current = null;
      setScanning(false);
    }
  };

  const startScanner = async () => {
    if (!videoRef.current || scannerRef.current) return;
    try {
      const { Html5Qrcode } = await import("html5-qrcode");
      const scanner = new Html5Qrcode("medtour-qr-reader");
      scannerRef.current = scanner;

      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 250, height: 250 } },
        (decodedText: string) => {
          handleScanResult(decodedText);
        },
        () => {
          // scan errors are frequent on every frame — ignore
        },
      );
      setScanning(true);
    } catch (err: any) {
      console.error("Camera start failed:", err);
      // Clear the ref so a retry (or the effect above) can start it again.
      scannerRef.current = null;
      const name = err?.name || String(err?.message || "");
      const denied =
        name.includes("NotAllowed") ||
        name.includes("Permission") ||
        /permission/i.test(String(err?.message || ""));
      toast.error(
        denied
          ? "Camera permission denied. Allow camera access in your browser's site settings, then try again."
          : "Camera unavailable — check it isn't in use by another app, or enter the code manually.",
      );
      setMode("manual");
    }
  };

  const handleScanResult = async (raw: string) => {
    await stopScanner();
    await verifyAndComplete(raw.trim());
  };

  const verifyAndComplete = async (payload: string) => {
    if (!payload) return;
    setVerifying(true);
    try {
      const res = await api.post("/doctor/scan", { qr_payload: payload });
      const { success, message, notes, appointment } = res.data;

      // The server refuses the check-in rather than throwing when the
      // appointment id in the QR doesn't match the code, there is no
      // diagnosis yet, or the code is unknown. Surface WHY, leave the
      // visit alone, and keep the modal open so another code can be tried.
      if (!success) {
        toast.error(message || "Appointment not checked in.", {
          description: notes || "The QR could not be verified.",
          duration: 10000,
        });
        setErrorNotes(notes || null);
        return;
      }

      toast.success(message || "Appointment verified!");
      setErrorNotes(null);
      // The server returns status only; the diagnosis is recovered from the
      // payload the patient just scanned, because it was never stored.
      onScanSuccess(appointment, extractClinical(payload));
      onClose();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Scan verification failed.";
      setErrorNotes(typeof msg === "string" ? msg : "Scan verification failed.");
      toast.error(msg);
    } finally {
      setVerifying(false);
    }
  };

  const handleManualSubmit = () => {
    if (!manualCode.trim()) {
      toast.error("Please enter the appointment code.");
      return;
    }
    verifyAndComplete(manualCode.trim());
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="rounded-2xl max-w-md p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-5 pt-5 pb-3 border-b border-border">
          <DialogTitle className="text-base font-bold flex items-center gap-2">
            <FiCamera className="h-4 w-4 text-primary" />
            Scan Doctor's QR Code
          </DialogTitle>
        </DialogHeader>

        <div className="p-5 space-y-4">
          {/* Why the previous attempt was refused — shown instead of silently
              leaving the visit untouched. */}
          {errorNotes && (
            <div className="rounded-xl border-2 border-amber-500/40 bg-amber-500/10 p-3 text-xs leading-relaxed">
              <p className="font-extrabold text-amber-700 dark:text-amber-400 mb-1">
                Not checked in
              </p>
              <p className="text-muted-foreground">{errorNotes}</p>
            </div>
          )}

          {verifying ? (
            <div className="py-8 flex flex-col items-center justify-center space-y-3 text-center animate-in fade-in">
              <div className="h-14 w-14 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
                <div className="h-7 w-7 rounded-full border-3 border-primary border-t-transparent animate-spin" />
              </div>
              <div>
                <h4 className="text-base font-extrabold text-foreground">Decrypting & Verifying Record</h4>
                <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
                  Deriving cryptographic key from aID, unpacking AES-256-GCM discharge payload & updating local ledger...
                </p>
              </div>
            </div>
          ) : mode === "camera" ? (
            <>
              {/* Camera viewport */}
              <div className="relative rounded-2xl overflow-hidden border-2 border-primary/30 bg-black aspect-square">
                <div id="medtour-qr-reader" ref={videoRef} className="w-full h-full" />
                {!scanning && (
                  <div className="absolute inset-0 grid place-items-center">
                    <p className="text-white text-sm animate-pulse">Starting camera…</p>
                  </div>
                )}
              </div>
              <Button
                onClick={() => {
                  stopScanner();
                  setMode("manual");
                }}
                variant="outline"
                className="w-full rounded-xl font-bold text-xs"
              >
                Switch to Manual Entry
              </Button>
            </>
          ) : (
            <>
              {/* Manual entry */}
              <div className="text-center space-y-3 py-2">
                <FiKey className="h-10 w-10 text-primary mx-auto" />
                <p className="text-sm text-muted-foreground">
                  Enter the appointment code shown on the doctor's screen.
                </p>
              </div>
              <Input
                placeholder="e.g. MT-1A2B3C4D"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleManualSubmit()}
                className="rounded-xl text-center font-mono font-bold text-sm tracking-wider h-12"
              />
              <Button
                onClick={handleManualSubmit}
                disabled={verifying}
                className="w-full h-11 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-extrabold text-sm"
              >
                Verify & Complete Appointment
              </Button>
              <Button
                onClick={() => setMode("camera")}
                variant="outline"
                className="w-full rounded-xl font-bold text-xs flex items-center justify-center gap-1.5"
              >
                <FiCamera className="h-3.5 w-3.5" /> Use Camera Instead
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
