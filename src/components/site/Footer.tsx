import { Link } from "@tanstack/react-router";

interface FooterProps {
  isTech?: boolean;
}

export function Footer({ isTech = false }: FooterProps) {
  return (
    <footer className={`border-t py-12 transition-colors duration-500 ${
      isTech 
        ? "border-neutral-800 text-neutral-400" 
        : "border-gray-100 text-gray-500"
    }`}>
      <div className="max-w-4xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-6 text-xs font-mono">
        
        {/* Brand & Mission Statement */}
        <div className="flex items-center gap-3">
          <span className={`font-black text-sm tracking-tight transition-colors ${
            isTech ? "text-white" : "text-black"
          }`}>
            MedTour
          </span>
          <span className="opacity-30">/</span>
          <span className="text-[11px] font-normal tracking-wide">
            {isTech ? "Deterministic Healthcare Gateway" : "Emergency Assistance in India"}
          </span>
        </div>

        {/* Minimal Text Links */}
        <div className="flex items-center gap-6">
          <Link 
            to="/" 
            className={`transition-colors ${
              isTech ? "hover:text-white" : "hover:text-black"
            }`}
          >
            Emergency
          </Link>
          <Link 
            to="/walk-in" 
            className={`transition-colors ${
              isTech ? "hover:text-white" : "hover:text-black"
            }`}
          >
            Clinics
          </Link>
          <a 
            href="tel:112" 
            className={`transition-colors ${
              isTech ? "hover:text-white" : "hover:text-black"
            }`}
          >
            SOS 112
          </a>
        </div>

        {/* Copyright & Open Standard */}
        <div className="text-[11px] opacity-60">
          © {new Date().getFullYear()} • Zero Sign-Up
        </div>

      </div>
    </footer>
  );
}
