import React, { useState, useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { 
  User, 
  Terminal, 
  ArrowRight, 
  Github, 
  ExternalLink, 
  Shield, 
  Activity, 
  MapPin, 
  Code, 
  Database, 
  Lock,
  HeartPulse,
  PhoneCall,
  Sparkles,
  HelpCircle,
  Plus,
  Stethoscope
} from "lucide-react";
import { Footer } from "@/components/site/Footer";

export const Route = createFileRoute("/landing")({
  head: () => ({
    meta: [
      { title: "MedTour — Instinctive Healthcare & Emergency Gateway for Travellers" },
      { 
        name: "description", 
        content: "Dual-mode emergency healthcare helper for foreign tourists in India. Light-themed plain English and dark-themed technical architectural specifications." 
      },
    ],
  }),
  component: LandingPage,
});

const contentData = {
  plain: {
    hero: {
      eyebrow: "MedTour",
      title: "SURVIVE THE UNEXPECTED",
      subtitle: (
        <>
          Your emergency healthcare helper for foreign tourists in India. Tap once to <span className="underline decoration-black/30 underline-offset-4 font-normal">call 112</span>, route to the <strong className="font-semibold text-black">nearest ER</strong>, and get a <em className="italic">translated taxi driver card</em>.
        </>
      ),
    },
    whatItIs: {
      title: "WHAT IT IS",
      heading: "The Panic Button for Travelers",
      paragraphs: [
        (
          <>
            Imagine you&apos;re a traveler in Mumbai: you feel suddenly very sick, you <em className="italic">don&apos;t speak Hindi</em>, and you don&apos;t know where the nearest hospital is. <strong className="font-semibold text-black">MedTour is the app you open.</strong>
          </>
        ),
        (
          <>
            It <span className="underline decoration-rose-500/50 underline-offset-4 font-medium text-black">instantly calls 112</span>, displays your exact GPS in high-contrast text, locates the <strong className="font-semibold text-black">nearest verified emergency room</strong>, and generates an emergency <em className="italic font-medium text-black">&ldquo;take me to the hospital&rdquo;</em> card translated into Hindi and Marathi.
          </>
        ),
        (
          <>
            Later, it helps you download audit-ready receipts to <strong className="font-semibold text-black">claim money back</strong> from your travel insurer. <span className="underline decoration-black/40 underline-offset-4 font-semibold">Zero account signup required.</span>
          </>
        )
      ],
      features: [
        { icon: MapPin, title: "Locate", desc: "Finds the nearest verified emergency room instantly." },
        { icon: Activity, title: "Triage", desc: "AI-driven symptom analysis to direct you to the right specialist." }
      ]
    },
    philosophy: {
      title: "THE GOLDEN 60 SECONDS",
      heading: "No waiting. No accounts.",
      paragraphs: [
        (
          <>
            In an emergency, every critical action must be <strong className="font-semibold text-black">exactly one tap away</strong>. We designed MedTour to execute <span className="underline decoration-black/30 underline-offset-4">before you even touch a sign-up form</span>.
          </>
        ),
        (
          <>
            <strong className="font-semibold text-black">We never fake dispatch.</strong> If an ambulance was not dispatched, we state it transparently. We route you directly to <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-gray-100 text-black">112</span>, <em className="italic">Google Maps</em>, and <em className="italic">Uber</em>, rather than creating fragile mock dispatch wrappers.
          </>
        ),
        (
          <>
            If your mobile internet drops, the <strong className="font-semibold text-black underline decoration-emerald-500/50 underline-offset-4">core emergency path still works 100% offline</strong> through cellular voice bands.
          </>
        )
      ]
    },
    vault: {
      title: "OFFLINE VAULT",
      heading: "Military-grade privacy.",
      paragraphs: [
        (
          <>
            Your medical records <strong className="font-semibold text-black">never touch a cloud database</strong> unencrypted. You can export your full medical ID as an encrypted <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-gray-100 text-black">.mtr</span> file locked with your personal passphrase.
          </>
        ),
        (
          <>
            Carry it on a USB flash drive or phone, and decrypt it on any browser. If an attacker attempts to brute-force the passphrase, <em className="italic">honey-decryption decoys</em> feed them <strong className="font-semibold text-black">corrupted gibberish</strong> instead of your records.
          </>
        ),
        (
          <>
            Your visits ledger and insurance claims remain <span className="underline decoration-black/30 underline-offset-4 font-medium text-black">your sovereign patient copy</span>, ready for download anytime.
          </>
        )
      ]
    },
    faq: {
      title: "QUESTIONS & ANSWERS",
      heading: "Everything you need to know.",
      items: [
        {
          q: "Do I need to sign up or create an account during an emergency?",
          a: "No. MedTour is strictly guest-first. You can trigger emergency 112 calls, locate verified emergency rooms, and download bilingual driver cards with zero registration or logins."
        },
        {
          q: "What happens if my mobile internet or cellular data fails?",
          a: "Emergency phone links (tel:112) and offline cached medical directions remain operational even without network access. Cached hospital directories load from your browser storage."
        },
        {
          q: "How does the Hindi/Marathi taxi emergency card work?",
          a: "It produces a full-screen, high-contrast digital card written in native Devanagari script explaining that you are having an acute medical emergency and displaying the exact ER destination for the driver."
        },
        {
          q: "How are my health records kept safe in the Vault?",
          a: "Records are encrypted on your device with military-grade AES-256-GCM using your personal passphrase before ever leaving your phone. You can carry your .mtr file anywhere with zero cloud leaks."
        },
        {
          q: "Can I use MedTour receipts for my travel insurance claim?",
          a: "Yes. All doctor visits, prescription records, and emergency expenses tracked in your local visits ledger can be exported into an itemized, audit-ready summary for overseas travel insurance providers."
        }
      ]
    }
  },
  tech: {
    hero: {
      eyebrow: "Architecture",
      title: "ZERO-AUTH GATEWAY.",
      subtitle: (
        <>
          A guest-first <strong className="font-semibold text-white">React 19 SPA</strong> backed by <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-white">FastAPI</span> and <strong className="font-semibold text-white">PostgreSQL</strong>. Bounding-box SQL routing, <em className="italic">deterministic offline fallbacks</em>, and <span className="underline decoration-white/40 underline-offset-4">honest API contracts</span>.
        </>
      ),
    },
    whatItIs: {
      title: "SYSTEM ARCHITECTURE",
      heading: "Patient-Side Integration",
      paragraphs: [
        (
          <>
            MedTour is an <strong className="font-semibold text-white">Emergency Medical Passport &amp; Urgent Triage Gateway</strong> constructed with <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 border border-neutral-800 text-white">TanStack Router</span>, React 19, and Tailwind v4. The backend runs on an asynchronous <strong className="font-semibold text-white">FastAPI + SQLAlchemy</strong> stack.
          </>
        ),
        (
          <>
            We ingest geospatial nodes from <em className="italic text-white">OpenStreetMap Overpass</em>, <em className="italic text-white">Geoapify</em>, and <em className="italic text-white">Nominatim</em>, <span className="underline decoration-white/40 underline-offset-4">strictly deduplicating</span> records before committing new facilities into PostgreSQL.
          </>
        ),
        (
          <>
            The <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-white">/emergency/sos</span> endpoint responds with an authoritative dispatch packet containing nearest ER name, distance, and ETA, <strong className="font-semibold text-white underline decoration-white/50 underline-offset-4">without ever logging fake dispatch records</strong>.
          </>
        )
      ],
      features: [
        { icon: Database, title: "Bounding-Box", desc: "14.3x faster /hospitals/nearby lookups using optimized SQL." },
        { icon: Code, title: "Offline Fallback", desc: "tel:112 and local /nearby routes render with zero network." }
      ]
    },
    philosophy: {
      title: "GUEST-FIRST DOCTRINE",
      heading: "localStorage as Primary.",
      paragraphs: [
        (
          <>
            All emergency capabilities are executable from the root path with <strong className="font-semibold text-white">zero required authentication</strong>. <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-white">localStorage</span> and IndexedDB serve as primary datastores; JWT tokens are purely optional.
          </>
        ),
        (
          <>
            We leverage native OS deep links (<span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 text-white">tel:</span>, <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 text-white">uber://</span>, and <em className="italic">Google Maps URLs</em>) rather than building fragile internal dispatch wrappers.
          </>
        ),
        (
          <>
            The system executes <strong className="font-semibold text-white">deterministic rule-based triage</strong> alongside <em className="italic text-white">NVIDIA NIM LLM</em> clinical drafting, <span className="underline decoration-white/40 underline-offset-4">falling back gracefully offline</span> if upstream inference is unreachable.
          </>
        )
      ]
    },
    vault: {
      title: "ENCRYPTION SPECS",
      heading: "AES-GCM-256 Vaults.",
      paragraphs: [
        (
          <>
            The <span className="font-mono text-xs px-1.5 py-0.5 rounded bg-neutral-900 border border-neutral-700 text-white">.mtr</span> vault executes <strong className="font-semibold text-white">PBKDF2-HMAC-SHA512 with 250,000 iterations</strong> and a <span className="underline decoration-white/40 underline-offset-4">32-byte CSPRNG salt</span> to derive a 256-bit AES key.
          </>
        ),
        (
          <>
            Envelopes feature a 32-byte salt, 12-byte IV, and <strong className="font-semibold text-white">SHA-256 HMAC integrity checksum</strong> with domain binding (<span className="font-mono text-xs px-1 py-0.5 rounded bg-neutral-900 text-neutral-300">urn:medtour:web:gateway</span>). Key derivation failure triggers <em className="italic text-white font-medium">honey decryption</em> with randomized decoys.
          </>
        ),
        (
          <>
            Client-side decryption uses audited <strong className="font-semibold text-white">@noble/ciphers</strong> in pure JS, eliminating browser Web Crypto security-origin locks on mobile LAN connections.
          </>
        )
      ]
    },
    faq: {
      title: "TECHNICAL FAQ",
      heading: "Specs & Cryptographic Guarantees.",
      items: [
        {
          q: "What cryptographic standards back the .mtr vault format?",
          a: "The vault uses AES-256-GCM authenticated encryption. Key derivation is powered by PBKDF2-HMAC-SHA512 with 250,000 iterations and a 32-byte CSPRNG salt. Envelopes include domain-separated HMAC integrity checksums (urn:medtour:web:gateway)."
        },
        {
          q: "How does honey decryption protect against offline brute-force attacks?",
          a: "If an incorrect passphrase is submitted, rather than halting with a distinguishable timing error, the system outputs convincing decoy structures and corrupted gibberish, exhausting unauthorized attackers."
        },
        {
          q: "How does hospital geospatial routing achieve high speed?",
          a: "The backend uses PostgreSQL bounding-box bounding queries with haversine distance filtering over deduplicated geospatial nodes (OpenStreetMap Overpass, Geoapify, Nominatim), delivering sub-15ms responses."
        },
        {
          q: "Why use Noble JS (@noble/ciphers) instead of Web Crypto API on client?",
          a: "Web Crypto requires secure contexts (HTTPS/localhost). For field testing or local area networks (LAN IPs on smartphones), Web Crypto is restricted by modern browsers. Pure-JS audited Noble packages ensure 100% deterministic portability."
        },
        {
          q: "Is any patient telemetry or location saved to backend logs?",
          a: "Zero unauthorized logging. The emergency dispatcher endpoints calculate distance and ETA statelessly in memory. Emergency payloads and patient IDs reside strictly inside browser localStorage/IndexedDB."
        }
      ]
    }
  }
};

interface SectionProps {
  id?: string;
  title: string;
  heading: string;
  paragraphs: React.ReactNode[];
  features?: Array<{ icon: any; title: string; desc: string }>;
  isTech: boolean;
}

const Section: React.FC<SectionProps> = ({ id, title, heading, paragraphs, features, isTech }) => (
  <section id={id} className="min-h-[70vh] flex flex-col relative pb-32 scroll-mt-6">
    {/* Sticky Section Header */}
    <div className={`sticky top-0 z-30 py-6 mb-16 border-b backdrop-blur-xl transition-colors duration-500 ${
      isTech 
        ? "bg-black/90 border-neutral-800 text-white" 
        : "bg-white/90 border-gray-100 text-gray-400"
    }`}>
      <h2 className="text-xs font-bold tracking-[0.25em] uppercase text-center font-mono">
        {title}
      </h2>
    </div>
    
    <div className="max-w-4xl mx-auto px-6 w-full flex-1 flex flex-col justify-center">
      <h3 className={`text-4xl md:text-5xl font-medium tracking-tight mb-12 text-center transition-colors duration-500 ${
        isTech ? "text-white" : "text-black"
      }`}>
        {heading}
      </h3>
      
      <div className={`space-y-8 text-lg md:text-xl leading-relaxed font-light text-justify max-w-3xl mx-auto transition-colors duration-500 ${
        isTech ? "text-neutral-300" : "text-gray-600"
      }`}>
        {paragraphs.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>

      {features && (
        <div className="grid grid-cols-2 gap-3.5 sm:gap-6 mt-14 sm:mt-20 max-w-3xl mx-auto w-full">
          {features.map((feat, i) => (
            <div 
              key={i} 
              className={`flex flex-col items-center text-center p-4 sm:p-8 rounded-2xl sm:rounded-3xl border transition-all duration-500 ${
                isTech 
                  ? "bg-black border-neutral-800 text-white shadow-none" 
                  : "bg-gray-50 border-gray-100 text-black shadow-none"
              }`}
            >
              <feat.icon 
                className={`w-6 h-6 sm:w-8 sm:h-8 mb-3 sm:mb-6 ${isTech ? "text-white" : "text-black"}`} 
                strokeWidth={1.5} 
              />
              <h4 className={`text-base sm:text-lg font-medium mb-1.5 sm:mb-2 ${isTech ? "text-white" : "text-black"}`}>
                {feat.title}
              </h4>
              <p className={`text-xs sm:text-sm leading-relaxed ${isTech ? "text-neutral-400" : "text-gray-500"}`}>
                {feat.desc}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  </section>
);


interface FAQItem {
  q: string;
  a: string;
}

interface FAQSectionProps {
  id?: string;
  title: string;
  heading: string;
  items: FAQItem[];
  isTech: boolean;
}

const FAQSection: React.FC<FAQSectionProps> = ({ id, title, heading, items, isTech }) => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggleItem = (idx: number) => {
    setOpenIndex((prev) => (prev === idx ? null : idx));
  };

  return (
    <section id={id} className="min-h-[60vh] flex flex-col relative pb-32 scroll-mt-6">
      {/* Sticky Section Header */}
      <div className={`sticky top-0 z-30 py-6 mb-16 border-b backdrop-blur-xl transition-colors duration-500 ${
        isTech 
          ? "bg-black/90 border-neutral-800 text-white" 
          : "bg-white/90 border-gray-100 text-gray-400"
      }`}>
        <h2 className="text-xs font-bold tracking-[0.25em] uppercase text-center font-mono">
          {title}
        </h2>
      </div>

      <div className="max-w-3xl mx-auto px-6 w-full flex-1 flex flex-col justify-center">
        <h3 className={`text-4xl md:text-5xl font-medium tracking-tight mb-14 text-center transition-colors duration-500 ${
          isTech ? "text-white" : "text-black"
        }`}>
          {heading}
        </h3>

        {/* Minimalist Divider Accordion (Single Line Dividers with + / x Icon) */}
        <div className={`border-t divide-y transition-colors duration-500 ${
          isTech 
            ? "border-neutral-800 divide-neutral-800" 
            : "border-gray-200 divide-gray-200"
        }`}>
          {items.map((item, idx) => {
            const isOpen = openIndex === idx;

            return (
              <div key={idx} className="transition-colors">
                <button
                  type="button"
                  onClick={() => toggleItem(idx)}
                  className="w-full py-6 flex items-center justify-between text-left gap-6 cursor-pointer select-none group"
                  aria-expanded={isOpen}
                >
                  <span className={`text-lg sm:text-xl font-medium transition-colors ${
                    isTech 
                      ? isOpen ? "text-white font-semibold" : "text-neutral-300 group-hover:text-white" 
                      : isOpen ? "text-black font-semibold" : "text-neutral-700 group-hover:text-black"
                  }`}>
                    {item.q}
                  </span>
                  
                  {/* Plus / X Icon with Smooth 45 deg Rotation */}
                  <span className={`shrink-0 p-1 flex items-center justify-center transition-transform duration-300 ${
                    isOpen ? "rotate-45" : "rotate-0"
                  }`}>
                    <Plus 
                      className={`w-5 h-5 sm:w-6 sm:h-6 transition-colors ${
                        isTech 
                          ? isOpen ? "text-white" : "text-neutral-500 group-hover:text-neutral-300"
                          : isOpen ? "text-black" : "text-neutral-400 group-hover:text-neutral-700"
                      }`} 
                      strokeWidth={2} 
                    />
                  </span>
                </button>

                <div 
                  className={`grid transition-all duration-300 ease-in-out ${
                    isOpen ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
                  }`}
                >
                  <div className="overflow-hidden">
                    <p className={`pb-7 pt-1 text-base sm:text-lg leading-relaxed font-light text-justify transition-colors ${
                      isTech 
                        ? "text-neutral-400 font-mono text-sm sm:text-base leading-relaxed" 
                        : "text-neutral-600"
                    }`}>
                      {item.a}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

function LandingPage() {
  const navigate = useNavigate();
  const [isTech, setIsTech] = useState(false);
  const [fadeKey, setFadeKey] = useState(0);
  const [activeSection, setActiveSection] = useState<"what-it-is" | "philosophy" | "vault" | "faq">("what-it-is");

  // Trigger smooth transition animation when toggling modes
  useEffect(() => {
    setFadeKey((prev) => prev + 1);
  }, [isTech]);

  const isClickScrolling = React.useRef(false);

  // Observer to track which section is currently in view (debounced with requestAnimationFrame)
  useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (isClickScrolling.current) return;
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const s1 = document.getElementById("section-what-it-is");
          const s2 = document.getElementById("section-philosophy");
          const s3 = document.getElementById("section-vault");
          const s4 = document.getElementById("section-faq");

          const scrollPos = window.scrollY + window.innerHeight * 0.4;
          if (s4 && scrollPos >= s4.offsetTop) {
            setActiveSection("faq");
          } else if (s3 && scrollPos >= s3.offsetTop) {
            setActiveSection("vault");
          } else if (s2 && scrollPos >= s2.offsetTop) {
            setActiveSection("philosophy");
          } else {
            setActiveSection("what-it-is");
          }
          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const activeData = isTech ? contentData.tech : contentData.plain;

  const scrollToSection = (id: string, sectionKey: "what-it-is" | "philosophy" | "vault" | "faq") => {
    setActiveSection(sectionKey);
    isClickScrolling.current = true;
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
    setTimeout(() => {
      isClickScrolling.current = false;
    }, 600);
  };

  const navSections = [
    {
      id: "section-what-it-is",
      key: "what-it-is" as const,
      label: isTech ? "Architecture" : "Overview",
      icon: Activity,
    },
    {
      id: "section-philosophy",
      key: "philosophy" as const,
      label: isTech ? "Doctrine" : "60 Seconds",
      icon: Shield,
    },
    {
      id: "section-vault",
      key: "vault" as const,
      label: isTech ? "Cipher Vault" : "Vault",
      icon: Lock,
    },
    {
      id: "section-faq",
      key: "faq" as const,
      label: isTech ? "Specs Q&A" : "FAQ",
      icon: HelpCircle,
    },
  ];

  return (
    <div className={`min-h-screen font-sans selection:bg-neutral-800 selection:text-white pb-36 transition-colors duration-700 ${
      isTech 
        ? "bg-black text-white" 
        : "bg-white text-black"
    }`}>
      
      {/* =========================================================================
          BIG HERO SECTION WITH EMBEDDED CTAS (No Bouncing Line)
          ========================================================================= */}
      <section className="min-h-screen flex flex-col justify-center items-center px-6 relative text-center -mt-8 sm:-mt-12 pb-12">
        <div 
          key={`hero-${fadeKey}`} 
          className="max-w-5xl mx-auto text-center animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out"
        >
          <span className={`text-sm font-bold tracking-[0.25em] uppercase mb-8 block transition-colors duration-500 font-mono ${
            isTech ? "text-neutral-400" : "text-gray-400"
          }`}>
            {activeData.hero.eyebrow}
          </span>
          <h1 className={`text-6xl md:text-8xl lg:text-9xl font-semibold tracking-tighter leading-[0.9] mb-12 transition-colors duration-500 ${
            isTech ? "text-white" : "text-black"
          }`}>
            {activeData.hero.title}
          </h1>
          <p className={`text-xl md:text-2xl font-light max-w-2xl mx-auto leading-relaxed transition-colors duration-500 mb-12 ${
            isTech ? "text-neutral-300" : "text-gray-500"
          }`}>
            {activeData.hero.subtitle}
          </p>

          {/* PRIMARY & SECONDARY HERO CTAS */}
          <div className="max-w-2xl mx-auto w-full space-y-3.5">
            <button
              type="button"
              onClick={() => navigate({ to: "/" })}
              className={`w-full h-13 sm:h-14 px-7 rounded-full font-semibold text-sm transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer shadow-lg active:scale-95 whitespace-nowrap ${
                isTech
                  ? "bg-white text-black hover:bg-neutral-200 shadow-[0_4px_24px_rgba(255,255,255,0.15)]"
                  : "bg-black text-white hover:bg-neutral-800 shadow-[0_4px_20px_rgba(0,0,0,0.12)]"
              }`}
            >
              <Activity className="w-4 h-4 shrink-0" />
              <span>{isTech ? "Launch Emergency System" : "Launch Emergency App"}</span>
              <ArrowRight className="w-4 h-4 shrink-0 opacity-70" />
            </button>

            <div className="flex items-center justify-center gap-3.5">
              <button
                type="button"
                onClick={() => navigate({ to: "/walk-in" })}
                className={`flex-1 h-13 sm:h-14 px-5 rounded-full font-semibold text-sm transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer border active:scale-95 whitespace-nowrap ${
                  isTech
                    ? "border-neutral-800 bg-neutral-950 text-white hover:bg-neutral-900 hover:border-neutral-700"
                    : "border-gray-300/80 bg-white text-black hover:bg-gray-50 hover:border-black/30"
                }`}
              >
                <HeartPulse className="w-4 h-4 shrink-0 opacity-70" />
                <span>{isTech ? "Walk-In Specs" : "Find Clinics"}</span>
              </button>

              <button
                type="button"
                onClick={() => navigate({ to: "/doctor" })}
                className={`flex-1 h-13 sm:h-14 px-5 rounded-full font-semibold text-sm transition-all duration-300 flex items-center justify-center gap-2.5 cursor-pointer border active:scale-95 whitespace-nowrap ${
                  isTech
                    ? "border-white/15 bg-white/5 text-neutral-200 hover:bg-white/10 hover:border-white/30"
                    : "border-black/20 bg-black/5 text-black hover:bg-black/10 hover:border-black/40"
                }`}
              >
                <Stethoscope className="w-4 h-4 shrink-0 opacity-80" />
                <span>{isTech ? "Doctor Portal" : "Doctor Login"}</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          CONTENT STREAM (Structural Sticky Section Headers with IDs)
          ========================================================================= */}
      <div key={`content-${fadeKey}`} className="animate-in fade-in duration-700 ease-out">
        <Section id="section-what-it-is" isTech={isTech} {...activeData.whatItIs} />
        <Section id="section-philosophy" isTech={isTech} {...activeData.philosophy} />
        <Section 
          id="section-vault"
          isTech={isTech} 
          {...activeData.vault} 
          features={
            isTech 
              ? [
                  { icon: Shield, title: "Honey Decryption", desc: "Integrity checksums prevent silent payload corruption." },
                  { icon: Lock, title: "PBKDF2 Derivation", desc: "250,000 iterations securely derive the master key." }
                ]
              : [
                  { icon: Shield, title: "Zero Knowledge", desc: "Your health records are never uploaded unencrypted." },
                  { icon: Lock, title: "Password Protected", desc: "Portable .mtr files locked with your master passphrase." }
                ]
          }
        />
        <FAQSection 
          id="section-faq" 
          isTech={isTech} 
          {...activeData.faq} 
        />
      </div>

      {/* Footer */}
      <div className="max-w-4xl mx-auto px-6 mt-16">
        <Footer isTech={isTech} />
      </div>

      {/* =========================================================================
          BOTTOM FLOATING CONTROL DOCK (Scaled Up, Responsive & Smooth)
          - Left Capsule: Section Nav matching Image Spec
          - Right Circle: Mode Toggle Button (Normal <-> Tech)
          ========================================================================= */}
      <div className="fixed bottom-5 sm:bottom-7 left-0 right-0 z-50 px-4 flex items-center justify-center pointer-events-none pb-[env(safe-area-inset-bottom)]">
        <div className="flex items-center gap-3 sm:gap-4 pointer-events-auto">
          
          {/* 1. Left Action Capsule: Pure Icon Buttons with Smooth Sliding Blob */}
          <div 
            className={`relative flex items-center p-2 rounded-full backdrop-blur-2xl border transition-colors duration-300 shrink-0 select-none gap-2.5 ${
              isTech 
                ? "bg-black/95 border-neutral-800 shadow-[0_16px_48px_rgba(0,0,0,0.85)]" 
                : "bg-white/95 border-gray-200/90 shadow-[0_16px_40px_rgba(0,0,0,0.12)]"
            }`}
          >
            {/* Sliding Organic Blob Pill */}
            <div
              style={{
                transform: `translate3d(${
                  activeSection === "what-it-is" 
                    ? "0px" 
                    : activeSection === "philosophy" 
                      ? "62px" 
                      : activeSection === "vault" 
                        ? "124px" 
                        : "186px"
                }, 0, 0)`,
              }}
              className={`absolute left-2 top-2 w-[52px] h-[52px] rounded-full transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)] pointer-events-none will-change-transform shadow-md ${
                isTech 
                  ? "bg-white shadow-[0_0_24px_rgba(255,255,255,0.35)]" 
                  : "bg-black shadow-[0_8px_24px_rgba(0,0,0,0.25)]"
              }`}
            />

            {navSections.map((sec) => {
              const isActive = activeSection === sec.key;
              const IconComp = sec.icon;

              return (
                <button
                  key={sec.key}
                  type="button"
                  onClick={() => scrollToSection(sec.id, sec.key)}
                  className={`relative z-10 w-[52px] h-[52px] rounded-full flex items-center justify-center cursor-pointer select-none border transition-colors duration-200 shrink-0 ${
                    isActive
                      ? isTech
                        ? "text-black border-transparent font-bold"
                        : "text-white border-transparent font-bold"
                      : isTech
                        ? "border-neutral-800 text-neutral-400 hover:text-white hover:border-neutral-700"
                        : "border-black/15 text-neutral-600 hover:text-black hover:border-black/50"
                  }`}
                  title={sec.label}
                  aria-label={sec.label}
                >
                  <IconComp className="w-6 h-6" strokeWidth={isActive ? 2.5 : 2} />
                </button>
              );
            })}
          </div>

          {/* 2. Right Pure Circular Toggle Button */}
          <button 
            type="button"
            onClick={() => setIsTech(!isTech)}
            className={`w-[68px] h-[68px] rounded-full flex items-center justify-center shadow-[0_16px_40px_rgba(0,0,0,0.14)] hover:scale-105 active:scale-95 transition-transform duration-200 cursor-pointer shrink-0 border select-none ${
              isTech 
                ? "bg-white text-black border-white shadow-[0_0_28px_rgba(255,255,255,0.3)]" 
                : "bg-black text-white border-black"
            }`}
            aria-label="Toggle Technical Mode"
            title={`Switch to ${isTech ? "Normal" : "Technical"} View`}
          >
            <div className="relative w-7 h-7 flex items-center justify-center pointer-events-none">
              <User 
                className={`absolute transition-all duration-300 ${
                  isTech ? "opacity-0 rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
                }`} 
                size={24}
                strokeWidth={2}
              />
              <Terminal 
                className={`absolute transition-all duration-300 ${
                  !isTech ? "opacity-0 -rotate-90 scale-50" : "opacity-100 rotate-0 scale-100"
                }`}
                size={24}
                strokeWidth={2}
              />
            </div>
          </button>

        </div>
      </div>

    </div>
  );
}
