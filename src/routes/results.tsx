import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Sparkles, MapPin, Clock, Shield, ArrowLeft } from "lucide-react";
import { HospitalCard } from "@/components/dashboard/HospitalCard";
import { Card } from "@/components/ui/card";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";

function ResultsPage() {
  const navigate = useNavigate();
  // Get data from sessionStorage (passed by dashboard on analyze)
  const [storedData] = useState(() => {
    try {
      const raw = sessionStorage.getItem("ai_analysis_result");
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.error("Failed to load result", e);
    }
    return null;
  });

  const aiResult = storedData as {
    specialty?: string;
    urgency?: string;
    summary?: string;
    firstAid?: string[];
    prerequisites?: string[];
    recommendedHospitals?: any[];
  } | null;

  if (!aiResult) {
    return (
      <div className="h-screen w-full bg-background flex flex-col items-center justify-center text-foreground p-4">
        <span className="text-2xl font-black text-primary mb-2">MedTour</span>
        <p className="text-muted-foreground mb-4">No analysis results found. Please describe your symptoms first.</p>
        <button onClick={() => navigate({ to: "/dashboard" })} className="px-4 py-2 bg-primary text-primary-foreground rounded-full text-sm font-semibold">
          Return to Dashboard
        </button>
      </div>
    );
  }

  // Deduplicate hospitals by unique ID or Name+City
  const uniqueHospitals = (aiResult.recommendedHospitals || []).filter(
    (h, index, self) =>
      index ===
      self.findIndex(
        (t) =>
          t.id === h.id ||
          (t.name?.trim().toLowerCase() === h.name?.trim().toLowerCase() &&
            (t.city || "").trim().toLowerCase() === (h.city || "").trim().toLowerCase())
      )
  );

  return (
    <div className="h-screen w-full bg-background overflow-y-auto select-none">
      {/* Top Navbar */}
      <header className="sticky top-0 z-20 w-full bg-background/80 backdrop-blur-md border-b border-border/40 px-4 sm:px-8 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button 
            onClick={() => navigate({ to: "/dashboard" })} 
            className="p-1.5 rounded-full hover:bg-muted text-muted-foreground mr-1"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <span className="text-xl font-black tracking-tight text-primary">MedTour</span>
          <span className="text-muted-foreground/40 hidden sm:inline">|</span>
          <span className="text-xs sm:text-sm font-bold text-muted-foreground hidden sm:inline">AI Medical Triage</span>
        </div>
        <button 
          onClick={() => navigate({ to: "/dashboard" })} 
          className="text-xs sm:text-sm font-bold bg-muted px-3 py-1.5 rounded-full hover:bg-muted/80 text-foreground transition-all"
        >
          New Triage
        </button>
      </header>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Triage Urgency & Summary Banner */}
        <Card className="p-5 rounded-2xl border border-border shadow-sm">
          <div className="flex items-center gap-2.5 mb-2">
            <span className={`px-3 py-0.5 rounded-full text-xs font-black uppercase tracking-wider ${
              aiResult.urgency === "EMERGENCY" 
                ? "bg-red-500 text-white" 
                : aiResult.urgency === "URGENT" 
                ? "bg-amber-500 text-white" 
                : "bg-emerald-500 text-white"
            }`}>
              {aiResult.urgency || "ROUTINE"}
            </span>
            <span className="text-xs text-muted-foreground font-semibold">
              Specialty: <strong className="text-foreground capitalize">{aiResult.specialty || "General Medicine"}</strong>
            </span>
          </div>
          <p className="text-sm sm:text-base font-medium text-foreground leading-relaxed">
            {aiResult.summary || "Medical triage summary not available."}
          </p>
        </Card>

        {/* First Aid & Pre-requisites in Accordion */}
        <section className="rounded-2xl border border-border bg-card p-4 sm:p-5 shadow-sm">
          <Accordion type="multiple" defaultValue={["first-aid", "prerequisites"]} className="w-full">
            
            {/* First Aid Accordion Item */}
            <AccordionItem value="first-aid" className="border-b-border/60">
              <AccordionTrigger className="text-base sm:text-lg font-bold hover:no-underline py-3">
                <span className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-emergency" />
                  First Aid Action Plan (Red Cross Manual)
                </span>
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-4">
                <ul className="space-y-2.5 text-xs sm:text-sm text-foreground/90">
                  {aiResult.firstAid?.map((step, i) => (
                    <li key={i} className="flex items-start gap-2.5 bg-muted/40 p-2.5 rounded-xl border border-border/40">
                      <span className="flex-shrink-0 h-5 w-5 rounded-full bg-emergency/10 text-emergency text-xs font-black flex items-center justify-center">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed">{step}</span>
                    </li>
                  )) || <li>No first aid steps available.</li>}
                </ul>
              </AccordionContent>
            </AccordionItem>

            {/* Prerequisites Accordion Item */}
            <AccordionItem value="prerequisites" className="border-b-0">
              <AccordionTrigger className="text-base sm:text-lg font-bold hover:no-underline py-3">
                <span className="flex items-center gap-2">
                  <Clock className="h-5 w-5 text-primary" />
                  Pre-requisites Before Hospital Arrival
                </span>
              </AccordionTrigger>
              <AccordionContent className="pt-2 pb-2">
                <ul className="space-y-2 text-xs sm:text-sm text-muted-foreground">
                  {aiResult.prerequisites?.map((item, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-primary font-bold">•</span>
                      <span>{item}</span>
                    </li>
                  )) || <li>Carry identification and prior medical reports.</li>}
                </ul>
              </AccordionContent>
            </AccordionItem>

          </Accordion>
        </section>

        {/* Recommended Hospitals List */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-foreground">
              Best Recommended Hospitals ({uniqueHospitals.length})
            </h2>
            <span className="text-xs text-muted-foreground">50%+ Match Ranked</span>
          </div>
          
          <div className="space-y-3">
            {uniqueHospitals.length > 0 ? (
              uniqueHospitals.map((h) => (
                <HospitalCard key={h.id} hospital={h} />
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No nearby hospitals matched the 50%+ threshold.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export const Route = createFileRoute("/results")({
  component: ResultsPage,
});
