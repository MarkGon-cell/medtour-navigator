import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  Building2,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  clearHistory,
  getHistory,
  removeHistory,
  timeAgo,
  type HistoryEntry,
} from "@/lib/history";

/**
 * Signed-in user's search / hospital-view / AI-triage history with
 * re-run and clear controls. Rendered at page level (outside the profile
 * dropdown) and opened via the `open` prop.
 */
export function HistoryDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<HistoryEntry[]>([]);

  const handleOpenChange = (next: boolean) => {
    if (next) setEntries(getHistory());
    onOpenChange(next);
  };

  const kindMeta = {
    triage: { icon: Sparkles, label: "AI triage" },
    hospital: { icon: Building2, label: "Viewed hospital" },
    search: { icon: Search, label: "Searched" },
  } as const;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="rounded-3xl border-border/70 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Search className="h-4 w-4 text-primary" />
            Search History
          </DialogTitle>
          <DialogDescription>
            Your recent hospital searches, views and AI triage runs.
          </DialogDescription>
        </DialogHeader>

        {entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No history yet. Search for a hospital or run an AI triage to get
            started.
          </p>
        ) : (
          <>
            <div className="max-h-[50vh] space-y-1 overflow-y-auto pr-1">
              {entries.map((entry) => {
                const meta = kindMeta[entry.kind];
                const Icon = meta.icon;

                return (
                  <div key={entry.id} className="group flex items-center gap-2">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-muted/60 text-muted-foreground">
                      <Icon className="h-4 w-4" />
                    </span>

                    <button
                      type="button"
                      onClick={() => {
                        onOpenChange(false);
                        if (entry.kind === "triage") {
                          navigate({ to: "/" });
                        } else {
                          navigate({ to: "/walk-in" });
                        }
                      }}
                      className="min-w-0 flex-1 rounded-lg px-1 py-1.5 text-left transition-colors hover:bg-muted/60"
                    >
                      <span className="block truncate text-sm font-semibold text-foreground">
                        {entry.label}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {meta.label}
                        {entry.detail ? ` · ${entry.detail}` : ""} · {timeAgo(entry.createdAt)}
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setEntries(removeHistory(entry.id))}
                      aria-label="Remove from history"
                      className="shrink-0 rounded-lg p-1.5 text-muted-foreground opacity-0 transition-all
                                 hover:bg-muted hover:text-destructive focus-visible:opacity-100
                                 group-hover:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>

            <button
              type="button"
              onClick={() => {
                clearHistory();
                setEntries([]);
              }}
              className="w-full rounded-xl border border-border/70 py-2 text-xs font-bold text-muted-foreground
                         transition-colors hover:border-destructive/40 hover:text-destructive"
            >
              Clear all history
            </button>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
