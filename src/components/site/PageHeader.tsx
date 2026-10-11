import type { ReactNode } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { ArrowLeft, ShieldAlert, type LucideIcon } from "lucide-react";
import { ProfileMenu } from "@/components/site/ProfileMenu";

interface PageHeaderProps {
  /** Page title shown as "MedTour | <title>" */
  title?: string;
  subtitle?: string;
  /** Small icon rendered before the title */
  icon?: LucideIcon;
  iconClassName?: string;
  /** Render the back arrow */
  showBack?: boolean;
  /** Where the back arrow goes — defaults to / */
  backTo?: "/" | "/walk-in" | "/visits" | "/landing";
  /** Right-hand side controls rendered before the profile menu */
  actions?: ReactNode;
  /** Hide the avatar menu (rare — e.g. when a page renders its own) */
  hideProfile?: boolean;
}

/**
 * Shared pill-shaped topbar used on secondary screens.
 */
export function PageHeader({
  title,
  subtitle,
  icon: Icon,
  iconClassName = "text-primary",
  showBack = true,
  backTo = "/",
  actions,
  hideProfile = false,
}: PageHeaderProps) {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 w-full px-3 py-3 sm:px-6">
      <div
        className="mx-auto flex min-h-12 max-w-7xl items-center justify-between gap-2 overflow-hidden rounded-full border border-border/60
                   bg-card/70 px-2.5 sm:px-4
                   shadow-[0_4px_20px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.15)]
                   backdrop-blur-md backdrop-saturate-150"
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {showBack && (
            <button
              type="button"
              onClick={() => navigate({ to: backTo })}
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border/60
                         bg-card/60 text-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Go back"
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
          )}

          {/* MedTour tag */}
          <Link to={"/landing" as any} className="flex shrink-0 items-center gap-1.5" title="MedTour landing page">
            <span className="grid h-7 w-7 place-items-center rounded-full bg-primary text-primary-foreground">
              <ShieldAlert className="h-4 w-4" />
            </span>
            <span className="text-sm font-black tracking-tight text-foreground sm:text-base">
              MedTour
            </span>
          </Link>

          {title && (
            <div className="flex min-w-0 flex-1 items-center gap-1.5">
              <span className="shrink-0 text-muted-foreground/30">|</span>
              {Icon && (
                <Icon className={`hidden h-4 w-4 shrink-0 sm:block ${iconClassName}`} />
              )}
              <div className="min-w-0 flex-1">
                <h1 className="truncate text-xs font-bold text-foreground sm:text-sm">
                  {title}
                </h1>
                {subtitle && (
                  <p className="hidden truncate text-[11px] text-muted-foreground sm:block">
                    {subtitle}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {actions}
          {!hideProfile && <ProfileMenu />}
        </div>
      </div>
    </header>
  );
}
