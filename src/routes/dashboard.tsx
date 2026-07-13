import { createFileRoute, Link } from "@tanstack/react-router";
import { DashboardSidebar } from "@/components/dashboard/Sidebar";
import { SearchBar } from "@/components/site/SearchBar";
import { NotificationDropdown } from "@/components/site/NotificationDropdown";
import { HospitalCard } from "@/components/dashboard/HospitalCard";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { mockAppointments, mockHospitals } from "@/lib/mock-data";
import {
  Ambulance,
  Search,
  Sparkles,
  MapPin,
  Calendar,
  Stethoscope,
  Pill,
  FileText,
  Phone,
  ArrowRight,
} from "lucide-react";

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — MedTour" },
      { name: "description", content: "Your travel-ready healthcare dashboard: SOS, AI hospital matches and appointments." },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  return (
    <div className="flex min-h-screen bg-muted/30">
      <DashboardSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-xl sm:px-6">
          <div className="flex-1 max-w-xl">
            <SearchBar placeholder="Search hospitals, specialties, symptoms…" />
          </div>
          <NotificationDropdown />
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-primary text-primary-foreground">AS</AvatarFallback>
          </Avatar>
        </header>

        <main className="flex-1 space-y-6 p-4 sm:p-6">
          {/* Welcome + SOS */}
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="overflow-hidden rounded-2xl border-0 shadow-soft lg:col-span-2">
              <div className="relative bg-gradient-hero p-6 text-white sm:p-8">
                <p className="text-sm text-white/80">Welcome back</p>
                <h1 className="mt-1 text-2xl font-bold sm:text-3xl">Namaste, Aarav 👋</h1>
                <p className="mt-2 max-w-lg text-sm text-white/85">
                  You're in <strong>New Delhi</strong>. 24 verified hospitals nearby, all systems ready.
                </p>
                <div className="mt-5 flex flex-wrap gap-2">
                  <Button variant="secondary" size="sm" className="text-primary"><Search className="mr-1 h-4 w-4" />Find care</Button>
                  <Button variant="outline" size="sm" className="border-white/30 bg-white/10 text-white hover:bg-white/20"><Sparkles className="mr-1 h-4 w-4" />AI Match</Button>
                </div>
              </div>
            </Card>

            <Card className="rounded-2xl border-emergency/30 bg-emergency/5 shadow-soft">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-emergency text-emergency-foreground shadow-soft">
                    <Ambulance className="h-5 w-5" />
                  </div>
                  <Badge className="bg-emergency text-emergency-foreground hover:bg-emergency">Live</Badge>
                </div>
                <h3 className="mt-4 text-lg font-semibold">Emergency SOS</h3>
                <p className="mt-1 text-sm text-muted-foreground">Route to the nearest emergency-ready hospital in one tap.</p>
                <Button size="lg" className="mt-4 w-full bg-emergency text-emergency-foreground hover:bg-emergency/90">
                  <Phone className="mr-2 h-4 w-4" /> Call SOS
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Feature cards */}
          <div className="grid gap-6 md:grid-cols-2">
            <Card className="rounded-2xl border-border/70">
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-primary/10 text-primary"><Search className="h-5 w-5" /></div>
                  <div>
                    <h3 className="font-semibold">Search Hospitals</h3>
                    <p className="text-xs text-muted-foreground">Filter by specialty, distance and rating.</p>
                  </div>
                </div>
                <div className="mt-4"><SearchBar /></div>
              </CardContent>
            </Card>

            <Card className="rounded-2xl border-border/70">
              <CardContent className="p-6">
                <div className="flex items-center gap-3">
                  <div className="grid h-11 w-11 place-items-center rounded-xl bg-mint/20 text-mint-foreground"><Sparkles className="h-5 w-5" /></div>
                  <div>
                    <h3 className="font-semibold">AI Recommendations</h3>
                    <p className="text-xs text-muted-foreground">Personalized to your symptoms & itinerary.</p>
                  </div>
                </div>
                <ul className="mt-4 space-y-2 text-sm">
                  {["Best for cardiology near you", "Budget-friendly multi-specialty", "English-speaking staff"].map((t) => (
                    <li key={t} className="flex items-center justify-between rounded-lg border border-border/70 bg-card px-3 py-2">
                      <span>{t}</span>
                      <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { icon: Stethoscope, label: "Book Doctor" },
              { icon: Pill, label: "Pharmacies" },
              { icon: FileText, label: "Records" },
              { icon: Calendar, label: "Appointments" },
            ].map((a) => (
              <Card key={a.label} className="cursor-pointer rounded-2xl border-border/70 transition-all hover:-translate-y-0.5 hover:shadow-elevated">
                <CardContent className="flex flex-col items-center gap-2 p-4 text-center">
                  <div className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10 text-primary"><a.icon className="h-5 w-5" /></div>
                  <span className="text-sm font-medium">{a.label}</span>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Nearby hospitals */}
          <section>
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Nearby Hospitals</h2>
                <p className="text-xs text-muted-foreground flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> Within 10 km of New Delhi</p>
              </div>
              <Button variant="ghost" size="sm">View all <ArrowRight className="ml-1 h-4 w-4" /></Button>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {mockHospitals.slice(0, 4).map((h) => <HospitalCard key={h.id} h={h} />)}
            </div>
          </section>

          {/* Appointments */}
          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Recent Appointments</h2>
              <Button variant="ghost" size="sm">See history</Button>
            </div>
            <Card className="rounded-2xl border-border/70">
              <div className="divide-y divide-border">
                {mockAppointments.map((a) => (
                  <div key={a.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 p-4 sm:grid-cols-[1fr_1fr_1fr_auto]">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{a.hospital}</p>
                      <p className="text-xs text-muted-foreground truncate">{a.doctor} · {a.specialty}</p>
                    </div>
                    <p className="hidden text-sm text-muted-foreground sm:block">{a.date}</p>
                    <div className="hidden sm:block">
                      <Badge
                        variant="outline"
                        className={
                          a.status === "Confirmed" ? "border-mint/40 bg-mint/10 text-mint-foreground" :
                          a.status === "Pending" ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300" :
                          "border-border bg-muted text-muted-foreground"
                        }
                      >{a.status}</Badge>
                    </div>
                    <Button variant="outline" size="sm">Details</Button>
                  </div>
                ))}
              </div>
            </Card>
          </section>

          <div className="pt-2 text-center text-xs text-muted-foreground">
            <Link to="/" className="hover:underline">← Back to landing</Link>
          </div>
        </main>
      </div>
    </div>
  );
}
