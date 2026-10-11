import { Link } from "@tanstack/react-router";
import { Menu, X, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { ProfileMenu } from "@/components/site/ProfileMenu";

const links = [
  { to: "/", label: "Home" },
  { to: "/#features", label: "Features" },
  { to: "/#how", label: "How it Works" },
  { to: "/#faq", label: "FAQ" },
  { to: "/#contact", label: "Contact" },
];

export function Navbar() {
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed top-0 z-50 w-full px-3 py-3 sm:px-6">
      {/* Pill-shaped navbar bar (mobile + desktop) */}
      <div
        className="mx-auto flex h-12 max-w-7xl items-center justify-between gap-2 rounded-full border border-border/60
                   bg-card/70 px-2.5 sm:px-4
                   shadow-[0_4px_20px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,0.15)]
                   backdrop-blur-md backdrop-saturate-150"
      >
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 shrink-0 pl-0.5">
          <div className="grid h-8 w-8 place-items-center rounded-full bg-primary text-primary-foreground shadow-soft">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <span className="text-lg font-black tracking-tight text-foreground">
            MedTour
          </span>
        </Link>

        {/* Desktop Pill Navigation */}
        <div className="hidden md:flex items-center gap-1 rounded-full bg-muted/40 px-1.5 py-1">
          {links.map((l) => (
            <a
              key={l.to}
              href={l.to}
              className="rounded-full px-3.5 py-1.5 text-sm font-medium text-muted-foreground/80
                        transition-all duration-200 outline-none hover:bg-card/80 hover:text-foreground
                        focus-visible:text-foreground"
            >
              {l.label}
            </a>
          ))}
        </div>

        {/* Desktop Profile dropdown (Upload Profile & Learn More) */}
        <div className="hidden md:flex items-center gap-2 shrink-0">
          <ProfileMenu />
        </div>

        {/* Mobile menu toggle — pill shaped */}
        <button
          className="md:hidden grid h-9 w-9 shrink-0 place-items-center rounded-full border border-border/60
                     bg-card/60 text-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
          aria-expanded={open}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile Drawer — floating pill panel */}
      <div
        className={`mx-auto max-w-7xl overflow-hidden rounded-3xl border border-border/60 bg-card/90
                    backdrop-blur-md shadow-lg md:hidden
                    transition-[max-height,opacity] duration-300 ease-in-out
                    ${open ? "mt-2 max-h-[80vh] opacity-100" : "max-h-0 opacity-0 pointer-events-none"}`}
      >
        <div className="px-3 pb-3 pt-2.5 space-y-1">
          {links.map((l) => (
            <a
              key={l.to}
              href={l.to}
              onClick={() => setOpen(false)}
              className="block rounded-full px-4 py-2.5 text-sm font-medium text-foreground/80 hover:text-foreground
                        hover:bg-muted/60 transition-all"
            >
              {l.label}
            </a>
          ))}
          <div className="pt-2 border-t border-border/60 flex justify-center">
            <ProfileMenu />
          </div>
        </div>
      </div>
    </header>
  );
}
