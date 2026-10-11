/**
 * Per-user search / triage history stored in localStorage.
 *
 * The backend has no history endpoint yet, so this keeps a lightweight local
 * record keyed to the signed-in user (falls back to "guest" when logged out).
 */

export type HistoryKind = "search" | "triage" | "hospital";

export interface HistoryEntry {
  id: string;
  kind: HistoryKind;
  /** Primary line — hospital name, search query or symptom text */
  label: string;
  /** Secondary line — city/state, specialty, etc. */
  detail?: string;
  hospitalId?: number;
  createdAt: number;
}

const PREFIX = "medtour_history:";
const USER_KEY = "medtour_user_id";
const MAX_ENTRIES = 30;

function storageKey(): string {
  if (typeof window === "undefined") return `${PREFIX}guest`;
  let tag = "guest";
  try {
    tag = localStorage.getItem(USER_KEY) || "guest";
  } catch {
    /* storage unavailable */
  }
  return `${PREFIX}${tag}`;
}

/** Bind history to the signed-in user (call after /profile resolves). */
export function setHistoryUser(userId: string | number | null): void {
  if (typeof window === "undefined") return;
  try {
    if (userId === null) localStorage.removeItem(USER_KEY);
    else localStorage.setItem(USER_KEY, String(userId));
  } catch {
    /* storage unavailable */
  }
}

export function getHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

/** Prepend an entry, dropping older duplicates, and cap the list size. */
export function addHistory(
  entry: Omit<HistoryEntry, "id" | "createdAt">
): HistoryEntry[] {
  const label = entry.label.trim();
  if (!label) return getHistory();

  const list = getHistory();
  const now = Date.now();
  const next: HistoryEntry = {
    ...entry,
    label,
    id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: now,
  };

  const deduped = list.filter(
    (e) =>
      !(e.kind === next.kind && e.label.toLowerCase() === next.label.toLowerCase())
  );
  const updated = [next, ...deduped].slice(0, MAX_ENTRIES);

  try {
    localStorage.setItem(storageKey(), JSON.stringify(updated));
  } catch {
    /* storage unavailable */
  }
  return updated;
}

export function removeHistory(id: string): HistoryEntry[] {
  const updated = getHistory().filter((e) => e.id !== id);
  try {
    localStorage.setItem(storageKey(), JSON.stringify(updated));
  } catch {
    /* storage unavailable */
  }
  return updated;
}

export function clearHistory(): void {
  try {
    localStorage.removeItem(storageKey());
  } catch {
    /* storage unavailable */
  }
}

export function timeAgo(timestamp: number): string {
  const seconds = Math.max(1, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(timestamp).toLocaleDateString();
}
