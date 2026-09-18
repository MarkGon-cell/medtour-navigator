import { Link, useRouterState } from "@tanstack/react-router";
import {
  Home,
  HeartPulse,
  Search,
  Sparkles,
  MapPin,
  Calendar,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

const items = [
  { to: "/dashboard", label: "Overview", icon: Home },
  { to: "/dashboard", label: "Hospitals", icon: Search, hash: "hospitals" },
  { to: "/dashboard", label: "AI Match", icon: Sparkles, hash: "ai" },
  { to: "/dashboard", label: "Nearby", icon: MapPin, hash: "nearby" },
  { to: "/dashboard", label: "Appointments", icon: Calendar, hash: "appts" },
];

export function DashboardSidebar() {
  const pathname = useRouterState({
    select: (s) => s.location.pathname,
  });

  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "hidden shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col",
        "transition-all duration-300",
        collapsed ? "w-20" : "w-64"
      )}
    >
      {/* HEADER */}
      <div
        className={cn(
          "flex h-16 items-center border-b border-sidebar-border",
          collapsed
            ? "justify-center px-3"
            : "justify-between px-6"
        )}
      >
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-hero text-white">
              <HeartPulse className="h-5 w-5" />
            </div>

            <span className="text-lg font-bold">
              MedTour
            </span>
          </div>
        )}

        {collapsed && (
          <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-hero text-white">
            <HeartPulse className="h-5 w-5" />
          </div>
        )}

        <button
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="grid h-9 w-9 place-items-center rounded-lg hover:bg-sidebar-accent"
          aria-label={
            collapsed
              ? "Expand sidebar"
              : "Collapse sidebar"
          }
        >
          {collapsed ? (
            <Menu className="h-5 w-5" />
          ) : (
            <X className="h-5 w-5" />
          )}
        </button>
      </div>

      {/* NAVIGATION */}
      <nav className="flex-1 space-y-1 p-3">
        {items.map((item, i) => {
          const active =
            i === 0 &&
            pathname === "/dashboard";

          return (
            <Link
              key={item.label}
              to={item.to}
              hash={item.hash}
              title={collapsed ? item.label : undefined}
              className={cn(
                "flex items-center rounded-xl py-2.5 text-sm font-medium transition-colors",
                collapsed
                  ? "justify-center px-2"
                  : "gap-3 px-3",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-soft"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />

              {!collapsed && (
                <span>{item.label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* BOTTOM */}
      <div className="border-t border-sidebar-border p-3">
        <Link
          to="/"
          title={collapsed ? "Settings" : undefined}
          className={cn(
            "flex items-center rounded-xl py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent",
            collapsed
              ? "justify-center px-2"
              : "gap-3 px-3"
          )}
        >
          <Settings className="h-4 w-4 shrink-0" />

          {!collapsed && <span>Settings</span>}
        </Link>

        <Link
          to="/login"
          title={collapsed ? "Sign out" : undefined}
          className={cn(
            "flex items-center rounded-xl py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent",
            collapsed
              ? "justify-center px-2"
              : "gap-3 px-3"
          )}
        >
          <LogOut className="h-4 w-4 shrink-0" />

          {!collapsed && <span>Sign out</span>}
        </Link>
      </div>
    </aside>
  );
}