import { createFileRoute, Link } from "@tanstack/react-router";
import { Navbar } from "@/components/site/Navbar";
import { Footer } from "@/components/site/Footer";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Sparkles,
  ShieldCheck,
  MapPin,
  Ambulance,
  Stethoscope,
  Languages,
  Search,
  Navigation,
  ArrowRight,
  Star,
} from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "MedTour — AI Healthcare Navigation for Travellers in India" },
      { name: "description", content: "Find verified hospitals, get AI-powered recommendations, and navigate to care during emergencies while travelling across India." },
      { property: "og:title", content: "MedTour — AI Healthcare Navigation for Travellers" },
      { property: "og:description", content: "AI-powered hospital discovery, emergency SOS and navigation for domestic and international tourists in India." },
    ],
  }),
  component: Landing,
});

const features = [
  { icon: ShieldCheck, title: "Verified Hospitals", desc: "Handpicked, credential-checked facilities across every major city in India." },
  { icon: Sparkles, title: "AI Recommendations", desc: "Get matched to the right specialists based on symptoms, budget and location." },
  { icon: Ambulance, title: "Emergency SOS", desc: "One-tap SOS with real-time routing to the nearest emergency-ready hospital." },
  { icon: MapPin, title: "Offline-friendly Maps", desc: "Navigate care even with patchy signal using OpenStreetMap tiles." },
  { icon: Languages, title: "Multilingual", desc: "English, Hindi and 8+ Indian languages, plus tourist-friendly translations." },
  { icon: Stethoscope, title: "Care Concierge", desc: "Appointment booking, second opinions and travel-adjusted follow-ups." },
];

const steps = [
  { n: "01", title: "Tell us your trip", desc: "Share your destination, dates and any known health conditions." },
  { n: "02", title: "Get AI-matched care", desc: "We surface verified hospitals and specialists near every stop." },
  { n: "03", title: "Navigate & book", desc: "Route to the hospital, book appointments and store medical records." },
];

function Landing() {
  return (
    <div className="min-h-screen bg-background">
      <Navbar />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-hero opacity-[0.08]" />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-20 sm:px-6 md:grid-cols-2 md:py-28">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground shadow-soft">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> AI-powered healthcare navigator
            </div>
            <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight sm:text-5xl md:text-6xl">
              Healthcare that travels with you across <span className="bg-gradient-hero bg-clip-text text-transparent">India</span>.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-muted-foreground">
              Find verified hospitals, get AI-powered recommendations, and reach emergency care in minutes — designed for domestic and international tourists.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="bg-gradient-hero text-white shadow-elevated hover:opacity-95">
                <Link to="/register">Get Started <ArrowRight className="ml-1 h-4 w-4" /></Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to="/dashboard">View Dashboard</Link>
              </Button>
            </div>
            <div className="mt-8 flex items-center gap-6 text-sm text-muted-foreground">
              <div className="flex items-center gap-1"><Star className="h-4 w-4 fill-amber-400 text-amber-400" /> 4.9 tourist rating</div>
              <div>500+ verified hospitals</div>
              <div>24/7 SOS</div>
            </div>
          </div>

          <div className="relative">
            <div className="absolute -inset-6 bg-gradient-hero opacity-20 blur-3xl" />
            <Card className="relative overflow-hidden rounded-3xl border-border/70 shadow-elevated">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground">Nearest emergency care</p>
                    <p className="text-lg font-semibold">Apollo Hospitals · 2.4 km</p>
                  </div>
                  <div className="rounded-xl bg-emergency px-3 py-1 text-xs font-semibold text-emergency-foreground">SOS Ready</div>
                </div>
                <div className="mt-4 aspect-[4/3] rounded-2xl bg-gradient-card p-4">
                  <div className="flex h-full w-full items-center justify-center rounded-xl border border-dashed border-primary/30 bg-background/60">
                    <div className="text-center">
                      <MapPin className="mx-auto h-10 w-10 text-primary" />
                      <p className="mt-2 text-sm text-muted-foreground">Live map preview</p>
                    </div>
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3">
                  {[
                    { icon: Ambulance, label: "SOS" },
                    { icon: Search, label: "Search" },
                    { icon: Navigation, label: "Route" },
                  ].map((a) => (
                    <div key={a.label} className="flex flex-col items-center gap-1 rounded-xl border border-border bg-card p-3 text-xs font-medium">
                      <a.icon className="h-4 w-4 text-primary" /> {a.label}
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">Everything a travelling patient needs</h2>
          <p className="mt-3 text-muted-foreground">Purpose-built for medical tourism — from first symptom to safe return home.</p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <Card key={f.title} className="group rounded-2xl border-border/70 transition-all hover:-translate-y-0.5 hover:shadow-elevated">
              <CardContent className="p-6">
                <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-hero text-white shadow-soft">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{f.desc}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="border-y border-border bg-muted/30 py-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">How it works</h2>
            <p className="mt-3 text-muted-foreground">Three simple steps to peace of mind on the road.</p>
          </div>
          <div className="mt-12 grid gap-6 md:grid-cols-3">
            {steps.map((s) => (
              <Card key={s.n} className="relative rounded-2xl border-border/70">
                <CardContent className="p-6">
                  <div className="text-4xl font-bold text-primary/20">{s.n}</div>
                  <h3 className="mt-2 text-lg font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{s.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <h2 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">Frequently asked questions</h2>
        <Accordion type="single" collapsible className="mt-10">
          {[
            { q: "Is MedTour free to use?", a: "Yes. Search, AI recommendations and SOS routing are free. Only premium concierge is paid." },
            { q: "Are hospitals verified?", a: "Every listed hospital is credential-checked and reviewed by our medical partners." },
            { q: "Does it work offline?", a: "Maps and nearest-hospital data are cached so core navigation works without signal." },
            { q: "Which languages are supported?", a: "English, Hindi, Tamil, Telugu, Bengali, Marathi and more, with tourist translations." },
          ].map((f, i) => (
            <AccordionItem key={i} value={`i-${i}`}>
              <AccordionTrigger className="text-left">{f.q}</AccordionTrigger>
              <AccordionContent className="text-muted-foreground">{f.a}</AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </section>

      {/* Contact CTA */}
      <section className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
        <Card className="overflow-hidden rounded-3xl border-0 shadow-elevated">
          <div className="relative bg-gradient-hero p-10 text-white sm:p-14">
            <h3 className="max-w-2xl text-3xl font-bold sm:text-4xl">Ready to travel India with a doctor in your pocket?</h3>
            <p className="mt-3 max-w-xl text-white/85">Join thousands of tourists who use MedTour for stress-free healthcare on the road.</p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Button asChild size="lg" variant="secondary" className="text-primary">
                <Link to="/register">Create free account</Link>
              </Button>
              <Button asChild size="lg" variant="outline" className="border-white/30 bg-white/10 text-white hover:bg-white/20">
                <a href="mailto:support@medtour.example">Talk to us</a>
              </Button>
            </div>
          </div>
        </Card>
      </section>

      <Footer />
    </div>
  );
}
