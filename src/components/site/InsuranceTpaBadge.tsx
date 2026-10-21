import React, { useState } from "react";
import { FiShield, FiInfo, FiCreditCard, FiCheckCircle, FiChevronDown, FiChevronUp } from "react-icons/fi";

export interface InsuranceTpaProfile {
  cashless_available: boolean;
  badge_label: string;
  tier: string;
  accepted_tpas: string[];
  intl_insurers_supported: string[];
  deposit_policy: string;
  instructions: string;
  direct_billing: boolean;
}

interface InsuranceTpaBadgeProps {
  profile?: InsuranceTpaProfile;
  hospitalName?: string;
}

export function InsuranceTpaBadge({ profile, hospitalName }: InsuranceTpaBadgeProps) {
  const [expanded, setExpanded] = useState(false);

  if (!profile) {
    return (
      <div className="p-2.5 rounded-xl bg-muted/40 border border-border/60 text-xs text-muted-foreground font-medium flex items-center justify-between">
        <span className="truncate text-[11px] sm:text-xs">English Speaking Staff • Cash / Card Accepted</span>
      </div>
    );
  }

  const isCashless = profile.cashless_available;

  return (
    <div className="rounded-xl border border-border/70 overflow-hidden bg-card/60 transition-all text-xs">
      <div 
        onClick={(e) => {
          e.stopPropagation();
          setExpanded((prev) => !prev);
        }}
        className={`p-2.5 flex items-center justify-between cursor-pointer select-none transition-colors ${
          isCashless ? "bg-emerald-500/10 hover:bg-emerald-500/15" : "bg-amber-500/10 hover:bg-amber-500/15"
        }`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <FiShield className={`h-4 w-4 shrink-0 ${isCashless ? "text-emerald-500" : "text-amber-500"}`} />
          <div className="truncate">
            <span className={`font-semibold ${isCashless ? "text-emerald-700 dark:text-emerald-400" : "text-amber-700 dark:text-amber-400"}`}>
              {profile.badge_label}
            </span>
            <span className="text-muted-foreground text-[10px] ml-1.5 hidden sm:inline">
              ({profile.tier})
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 text-[11px] text-muted-foreground shrink-0 font-medium ml-2">
          <span>Deposit Info</span>
          {expanded ? <FiChevronUp className="h-3.5 w-3.5" /> : <FiChevronDown className="h-3.5 w-3.5" />}
        </div>
      </div>

      {expanded && (
        <div className="p-3 border-t border-border/60 space-y-2 bg-muted/20 text-[11px] text-foreground/90">
          <div className="flex items-start gap-2">
            <FiCreditCard className="h-4 w-4 text-primary shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-foreground">Admission Deposit & Billing Policy</p>
              <p className="text-muted-foreground text-[11px] leading-relaxed mt-0.5">
                {profile.deposit_policy}
              </p>
            </div>
          </div>

          {profile.accepted_tpas && profile.accepted_tpas.length > 0 && (
            <div className="pt-1">
              <span className="font-medium text-muted-foreground">Supported TPAs: </span>
              <span className="font-semibold text-foreground">
                {profile.accepted_tpas.join(", ")}
              </span>
            </div>
          )}

          {profile.intl_insurers_supported && profile.intl_insurers_supported.length > 0 && (
            <div>
              <span className="font-medium text-muted-foreground">International Policies: </span>
              <span className="font-semibold text-foreground">
                {profile.intl_insurers_supported.join(", ")}
              </span>
            </div>
          )}

          <div className="pt-1.5 p-2 rounded-lg bg-background/80 border border-border/50 text-[10px] text-muted-foreground leading-normal flex items-start gap-1.5">
            <FiInfo className="h-3.5 w-3.5 shrink-0 text-primary mt-0.5" />
            <span>{profile.instructions}</span>
          </div>
        </div>
      )}
    </div>
  );
}
