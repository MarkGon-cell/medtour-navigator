import { Link, useRouterState } from "@tanstack/react-router";
import { Home, HeartPulse, Search, Sparkles, MapPin, Calendar, Settings, LogOut } from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { to: "/dashboard", label: "Overview", icon: Home },
  { to: "/dashboard", label: "Hospitals", icon: Search, hash: "hospitals" },
  { to: "/dashboard", label: "AI Match", icon: Sparkles, hash: "ai" },
  { to: "/dashboard", label: "Nearby", icon: MapPin, hash: "nearby" },
  { to: "/dashboard", label: "Appointments", icon: Calendar, hash: "appts" },
];

export function DashboardSidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  return (
    <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
      <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-6">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-hero text-white">
          <HeartPulse className="h-5 w-5" />
        </div>
        <span className="text-lg font-bold">MedTour</span>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {items.map((item, i) => {
          const active = i === 0 && pathname === "/dashboard";
          return (
            <Link
              key={item.label}
              to={item.to}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-soft"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        <Link to="/" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent">
          <Settings className="h-4 w-4" /> Settings
        </Link>
        <Link to="/login" className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground/70 hover:bg-sidebar-accent">
          <LogOut className="h-4 w-4" /> Sign out
        </Link>
      </div>
    </aside>
  );
}
