import { useEffect, useState } from "react";
import { FiDownload, FiX, FiEye, FiEyeOff } from "react-icons/fi";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

/**
 * Fired app-wide to ask the patient to save a fresh `.mtr` backup.
 * Detail carries the human-readable reason ("Visit completed", ...).
 */
export const MTR_BACKUP_EVENT = "medtour:prompt-mtr-backup";

/**
 * Ask for a `.mtr` backup. Call this after anything that changed the
 * patient's stored records: a completed visit, a purchased claim, a new
 * booking. The prompt is global so any route can raise it without owning
 * the dialog itself.
 */
export function promptMtrBackup(reason: string) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(
    new CustomEvent(MTR_BACKUP_EVENT, { detail: { reason } }),
  );
}

/**
 * The dialog that answers `promptMtrBackup`.
 *
 * Clinical detail never reaches the server — it lives only in this browser
 * and in the `.mtr` file the patient carries. So a change to those records
 * is worthless until it is written back to that file, which is why every
 * mutation raises this prompt rather than silently succeeding.
 *
 * The vault is encrypted with the patient's own passphrase, so the file can
 * only be produced after they type it here: the password is never sent
 * anywhere, it is used to encrypt locally before the download starts.
 */
export function MtrBackupPrompt() {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      const detail = (event as CustomEvent<{ reason?: string }>).detail || {};
      setReason(detail.reason || "Your records changed");
      setPassword("");
      setShowPassword(false);
      setOpen(true);
    };
    window.addEventListener(MTR_BACKUP_EVENT, onPrompt);
    return () => window.removeEventListener(MTR_BACKUP_EVENT, onPrompt);
  }, []);

  const close = () => {
    setOpen(false);
    setPassword("");
  };

  const exportNow = async () => {
    if (!password || password.trim().length < 4) {
      toast.error("Password must be at least 4 characters.");
      return;
    }
    setBusy(true);
    try {
      const { exportMtrDatabaseFile } = await import("@/lib/mtrDatabase");
      const res = await exportMtrDatabaseFile(password);
      toast.success(
        res.method === "share"
          ? "Ready! Choose where to save or share your .mtr backup."
          : "Encrypted .mtr backup downloaded.",
      );
      close();
    } catch (err: any) {
      toast.error(err?.message || "Failed to export .mtr file.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-70 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-sm rounded-3xl bg-card border border-border p-6 shadow-2xl space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-2xl bg-primary/10 flex items-center justify-center shrink-0">
              <FiDownload className="h-4.5 w-4.5 text-primary" />
            </div>
            <div>
              <h3 className="text-base font-extrabold text-foreground leading-tight">
                Save a fresh .mtr backup
              </h3>
              <p className="text-[11px] text-muted-foreground">{reason}</p>
            </div>
          </div>
          <button
            onClick={close}
            className="h-8 w-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground shrink-0"
            aria-label="Dismiss backup reminder"
          >
            <FiX className="h-4 w-4" />
          </button>
        </div>

        <p className="text-xs text-muted-foreground leading-relaxed">
          This visit's diagnosis and invoice exist only on this device. Download
          the <code className="font-bold text-foreground">.mtr</code> file now so
          a cleared browser, a lost phone or a new machine cannot take your
          records with it.
        </p>

        {busy ? (
          <div className="py-6 flex flex-col items-center justify-center space-y-3 text-center animate-in fade-in">
            <div className="h-12 w-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center">
              <div className="h-6 w-6 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            </div>
            <div>
              <h4 className="text-sm font-extrabold text-foreground">Encrypting .mtr Database</h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                Deriving PBKDF2 keys & sealing with military-grade AES-256-GCM...
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-foreground block">
                Vault password
              </label>
              <div className="relative flex items-center">
                <input
                  type={showPassword ? "text" : "password"}
                  autoFocus
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      exportNow();
                    }
                  }}
                  placeholder="Enter password (min 4 chars)..."
                  className="w-full h-10 pl-3 pr-10 rounded-xl border border-input bg-background text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 p-1 rounded-md text-muted-foreground hover:text-foreground transition-colors"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <FiEyeOff className="h-4 w-4" />
                  ) : (
                    <FiEye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div className="pt-1 flex gap-2">
              <Button
                variant="outline"
                onClick={close}
                className="flex-1 h-10 rounded-xl font-bold text-xs"
              >
                Later
              </Button>
              <Button
                onClick={exportNow}
                disabled={busy}
                className="flex-1 h-10 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-bold text-xs"
              >
                Encrypt & Download
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
