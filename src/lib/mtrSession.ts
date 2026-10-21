/**
 * `.mtr` session state — the single source of truth for "is the patient
 * signed in?".
 *
 * There are no patient accounts in MedTour: the docked `.mtr` vault (or an
 * active medical profile) IS the patient's identity. Booking an appointment
 * requires it, so scheduling buttons are disabled whenever this returns
 * false — the name and reason sent to the server come from that profile.
 */

const DOCKED_FLAG = "medtour_mtr_docked";
const MEDICAL_ID_KEY = "medtour_medical_id";

/**
 * True when a `.mtr` vault is docked or a medical profile with a real name
 * exists. Mirrors the gate the visits ledger uses, so the same conditions
 * decide both "can I see my visits" and "can I schedule one".
 */
export function isMtrSignedIn(): boolean {
  if (typeof window === "undefined") return false;

  try {
    if (localStorage.getItem(DOCKED_FLAG) === "true") return true;
  } catch {
    // Storage can throw in private/restricted modes — treat as signed out.
  }

  try {
    const raw = localStorage.getItem(MEDICAL_ID_KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return typeof parsed?.fullName === "string" && parsed.fullName.trim().length > 0;
  } catch {
    return false;
  }
}

/**
 * The patient's display name for a booking, from the stored medical profile.
 * Returns null when there is no usable name (callers must block the booking).
 */
export function getPatientName(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(MEDICAL_ID_KEY);
    if (!raw) return null;
    const name = JSON.parse(raw)?.fullName;
    return typeof name === "string" && name.trim() ? name.trim() : null;
  } catch {
    return null;
  }
}

/**
 * Pull the numeric hospital id out of a `Clinic.id`, which is either a raw
 * numeric id or the `api-<id>` form the AI triage results produce.
 * Returns null when the id can't be resolved (nothing to book against).
 */
export function parseHospitalId(clinicId: string | number | undefined | null): number | null {
  if (typeof clinicId === "number") return Number.isFinite(clinicId) ? clinicId : null;

  const raw = String(clinicId ?? "").trim();
  if (!raw) return null;

  // `api-123` → 123
  const prefixed = raw.match(/^api-(\d+)$/);
  if (prefixed) return Number(prefixed[1]);

  // Bare numeric string
  if (/^\d+$/.test(raw)) return Number(raw);

  return null;
}
