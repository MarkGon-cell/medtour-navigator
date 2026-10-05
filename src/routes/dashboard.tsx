import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState, useRef } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";  
import { Skeleton } from "@/components/ui/skeleton";
import { HospitalCardSkeleton } from "@/components/dashboard/HospitalCardSkeleton";
import { 
  Loader2, 
  Mic, 
  Sparkles, 
  MapPin, 
  CheckCircle2, 
  Shield, 
  HeartPulse, 
  Search,
  Crosshair,
  X,
  AlertCircle
} from "lucide-react";

import type { Hospital } from "@/lib/hospital-data";
import api from "@/lib/api";

interface LocationDetails {
  name: string;
  pincode: string;
  fullAddress: string;
}

const PRESET_LOCATIONS = [
  { name: "Vasai / Virar, Palghar", lat: 19.3719, lng: 72.8220, pincode: "401201" },
  { name: "Andheri, Mumbai", lat: 19.1136, lng: 72.8697, pincode: "400053" },
  { name: "Thane West, Mumbai", lat: 19.2183, lng: 72.9781, pincode: "400601" },
  { name: "Mumbai Central", lat: 18.9712, lng: 72.8197, pincode: "400008" },
  { name: "Navi Mumbai, Vashi", lat: 19.0771, lng: 72.9986, pincode: "400703" },
  { name: "Shivaji Nagar, Pune", lat: 18.5308, lng: 73.8475, pincode: "411005" },
];

async function getLocationDetails(
  latitude: number,
  longitude: number
): Promise<LocationDetails> {
  try {
    const response = await fetch(
      `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`
    );

    if (!response.ok) {
      throw new Error("Reverse geocoding failed");
    }

    const data = await response.json();
    const address = data.address || {};

    const local =
      address.suburb ||
      address.neighbourhood ||
      address.residential ||
      address.road ||
      address.village ||
      address.city_district;

    const city =
      address.city ||
      address.town ||
      address.municipality ||
      address.district ||
      address.county;

    const state = address.state;
    const pincode = address.postcode || "";

    const parts = [local, city, state].filter(Boolean);
    const locationName =
      parts.length > 0
        ? parts.join(", ")
        : data.display_name
        ? data.display_name.split(",").slice(0, 3).join(", ")
        : "Current Location";

    return {
      name: locationName,
      pincode: pincode,
      fullAddress: data.display_name || locationName,
    };
  } catch (error) {
    console.error("Failed to detect location name:", error);
    return {
      name: "Current Location",
      pincode: "",
      fullAddress: "Current Location",
    };
  }
}

interface AIResponse {
  firstAid: string[];
  prerequisites: string[];
  recommendedHospitals: Hospital[];
  specialty: string | null;
  urgency?: string;
  summary?: string;
}

function Dashboard() {
  const navigate = useNavigate();
  const [userLocationName, setUserLocationName] = useState("Detecting location...");
  const [userPincode, setUserPincode] = useState("");
  const [userFullAddress, setUserFullAddress] = useState("");
  const [hospitalError, setHospitalError] = useState("");
  const [userName, setUserName] = useState("User");
  const [symptoms, setSymptoms] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSendingSOS, setIsSendingSOS] = useState(false);
  const [sosDispatched, setSosDispatched] = useState(false);
  const [aiResult, setAiResult] = useState<AIResponse | null>(null);
  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number } | null>(null);
  
  // Location picker modal for HTTP/LAN or manual override
  const [showLocationPicker, setShowLocationPicker] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchingLoc, setIsSearchingLoc] = useState(false);

  const [isInputFocused, setIsInputFocused] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Monitor keyboard dismiss natively
  useEffect(() => {
    if (typeof window === "undefined" || !window.visualViewport) return;

    const vp = window.visualViewport;
    const handleViewportChange = () => {
      const isKeyboardOpen = window.innerHeight - vp.height > 100;
      if (!isKeyboardOpen && isInputFocused) {
        setIsInputFocused(false);
      }
    };

    vp.addEventListener("resize", handleViewportChange, { passive: true });
    return () => {
      vp.removeEventListener("resize", handleViewportChange);
    };
  }, [isInputFocused]);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/profile");
        setUserName(response.data.full_name || "User");
      } catch (error) {
        console.error("Failed to load user profile:", error);
      }
    };
    fetchProfile();
  }, []);

  const requestGPSLocation = () => {
    if (!navigator.geolocation) {
      setHospitalError("Geolocation is not supported by your browser.");
      setShowLocationPicker(true);
      return;
    }

    // Check for HTTP on non-localhost (Browsers block navigator.geolocation on insecure origins)
    const isHttpLan = window.location.protocol === "http:" && !["localhost", "127.0.0.1"].includes(window.location.hostname);

    toast("Requesting GPS access...", { duration: 1500 });
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          setHospitalError("");
          const latitude = position.coords.latitude;
          const longitude = position.coords.longitude;
          setUserCoords({ lat: latitude, lng: longitude });

          const details = await getLocationDetails(latitude, longitude);
          setUserLocationName(details.name);
          setUserPincode(details.pincode);
          setUserFullAddress(details.fullAddress);
          toast.success("GPS Location connected!");
        } catch (error) {
          console.error("Failed to fetch location details:", error);
          setUserLocationName("Current Location");
        }
      },
      (error) => {
        console.error("Location permission/error:", error);
        if (isHttpLan) {
          setHospitalError("Browser policy requires HTTPS for hardware GPS over WiFi IP. Please select your area below.");
        } else {
          setHospitalError("Location permission denied. Please allow GPS or select your area.");
        }
        setUserLocationName("Location required");
        setUserCoords(null);
        setShowLocationPicker(true);
      },
      { enableHighAccuracy: false, timeout: 6000, maximumAge: 30000 }
    );
  };

  useEffect(() => {
    requestGPSLocation();
  }, []);

  const selectManualLocation = (loc: { name: string; lat: number; lng: number; pincode?: string }) => {
    setUserCoords({ lat: loc.lat, lng: loc.lng });
    setUserLocationName(loc.name);
    setUserPincode(loc.pincode || "");
    setUserFullAddress(loc.name);
    setHospitalError("");
    setShowLocationPicker(false);
    toast.success(`Location set to: ${loc.name}`);
  };

  const handleSearchCustomLocation = async () => {
    if (!searchQuery.trim()) return;
    setIsSearchingLoc(true);
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(searchQuery)}&limit=1`);
      const data = await res.json();
      if (data && data.length > 0) {
        const item = data[0];
        selectManualLocation({
          name: item.display_name.split(",").slice(0, 3).join(", "),
          lat: parseFloat(item.lat),
          lng: parseFloat(item.lon),
        });
      } else {
        toast.error("Area not found. Try entering city or pincode.");
      }
    } catch (e) {
      toast.error("Location search failed. Please select from list.");
    } finally {
      setIsSearchingLoc(false);
    }
  };

  const userInitials = userName
    .split(" ")
    .map((name) => name[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleTriggerSOS = async () => {
    if (!userCoords) {
      setShowLocationPicker(true);
      toast.error("Please grant location access or pick your area before sending SOS.");
      return;
    }

    setIsSendingSOS(true);
    try {
      const payload = {
        latitude: userCoords.lat,
        longitude: userCoords.lng,
        address: userLocationName || userFullAddress || "Current GPS Location",
        pincode: userPincode || undefined,
        message: symptoms.trim() || "Emergency SOS triggered by user from MedTour Navigator",
        contact_emergency_services: true,
      };

      const response = await api.post("/emergency/sos", payload);
      setSosDispatched(true);
      toast.success("🚨 Emergency SOS Sent! Ambulance dispatch logged in backend.", {
        duration: 5000,
      });
      console.log("SOS Response:", response.data);
    } catch (error: any) {
      console.error("Failed to trigger SOS:", error);
      toast.error("SOS trigger failed. Please call 108 directly!");
    } finally {
      setIsSendingSOS(false);
    }
  };

  const analyzeSymptoms = async () => {
    if (!symptoms.trim()) return;
    if (!userCoords) {
      setShowLocationPicker(true);
      toast.error("Please select your area so we can match nearby hospitals.");
      return;
    }

    setIsAnalyzing(true);
    setAiResult(null);
    try {
      const response = await api.post("/ai/analyze", {
        symptoms: symptoms,
        latitude: userCoords.lat,
        longitude: userCoords.lng,
        radius_km: 20,
      });
      setAiResult(response.data);
      sessionStorage.setItem("ai_analysis_result", JSON.stringify(response.data));
      toast.success("AI Symptom Analysis complete!");
      navigate({ to: "/results" });
    } catch (error: any) {
      console.error("AI analysis failed:", error);
      setHospitalError(
        error.response?.data?.detail || "Unable to analyze symptoms. Please try again."
      );
      toast.error("Unable to analyze symptoms at the moment.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div ref={containerRef} className="min-h-[100dvh] h-[100dvh] w-full bg-background flex flex-col justify-between overflow-hidden select-none">
      
      {/* 1. Header (Compact) */}
      <header className="flex-shrink-0 w-full px-4 sm:px-6 py-2 flex items-center justify-between border-b border-border/40 bg-background/90 backdrop-blur-sm z-10 overflow-x-hidden">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg sm:text-xl font-black tracking-tight text-primary shrink-0">MedTour</span>
          <span className="text-muted-foreground/30 shrink-0">|</span>
          <h1 className="text-xs sm:text-sm font-bold text-foreground truncate">
            Namaste, {userName}
          </h1>
        </div>
        <Avatar className="h-7 w-7 sm:h-8 sm:w-8 ring-1 ring-primary/20 shadow-sm shrink-0">
          <AvatarFallback className="bg-primary text-primary-foreground text-xs font-bold">
            {userInitials}
          </AvatarFallback>
        </Avatar>
      </header>

      {/* 2. Main Body: Physical Flex Sizing (Smoothly & Automatically Scales as Keyboard Pushes Layout) */}
      <main className="flex-1 w-full flex flex-col items-center justify-center px-3 sm:px-4 max-w-lg mx-auto min-h-0 overflow-hidden">
        
        {/* Dynamic Physical Scaling SOS Button */}
        <div className="relative flex items-center justify-center max-w-full my-auto py-1 min-h-0">
          <div className="absolute inset-0 rounded-full bg-emergency/25 animate-ping opacity-35 duration-1000 pointer-events-none" />

          <button
            onClick={handleTriggerSOS}
            disabled={isSendingSOS}
            aria-label="Trigger Emergency SOS"
            className="group relative flex items-center justify-center rounded-full bg-red-600 shadow-[0_18px_50px_-8px_rgba(220,38,38,0.58),0_0_0_8px_rgba(220,38,38,0.12)] active:scale-95 hover:scale-[1.02] focus:outline-none focus:ring-4 focus:ring-emergency/40 cursor-pointer h-[min(52vw,30vh)] w-[min(52vw,30vh)] max-h-[22rem] max-w-[22rem] min-h-[4.5rem] min-w-[4.5rem] aspect-square"
          >
            <div className="flex flex-col items-center justify-center text-center">
              {isSendingSOS ? (
                <>
                  <Loader2 className="text-white animate-spin h-[min(8vw,5vh)] w-[min(8vw,5vh)] mb-1" />
                  <span className="text-[min(2.5vw,1.8vh)] font-bold text-white uppercase tracking-widest">
                    Dispatching...
                  </span>
                </>
              ) : sosDispatched ? (
                <>
                  <CheckCircle2 className="text-white animate-bounce h-[min(8vw,5vh)] w-[min(8vw,5vh)] mb-1" />
                  <span className="text-[min(5vw,3.5vh)] font-black text-white tracking-wider">
                    SENT
                  </span>
                  <span className="text-[min(2.2vw,1.5vh)] text-white/90 font-medium">
                    Ambulance Alerted
                  </span>
                </>
              ) : (
                <span className="text-[min(14vw,8.5vh)] font-black text-white tracking-[0.08em] drop-shadow-[0_4px_12px_rgba(0,0,0,0.35)] leading-none">
                  SOS
                </span>
              )}
            </div>
          </button>
        </div>

        {/* Location Status Pill / Interactive Trigger */}
        <div className="w-full flex flex-col items-center mt-1 sm:mt-2 mb-1 flex-shrink-0">
          {userCoords ? (
            <button
              onClick={() => setShowLocationPicker(true)}
              className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-300 dark:border-emerald-800/60 shadow-sm hover:opacity-90 transition-all max-w-[95%] cursor-pointer px-3 py-1 text-[11px] sm:text-xs"
            >
              <MapPin className="h-3 w-3 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
              <span className="font-bold text-emerald-700 dark:text-emerald-300 truncate">
                {userLocationName}
              </span>
              <span className="text-[9px] text-emerald-600/70 underline ml-1">Change</span>
            </button>
          ) : (
            <div className="w-full max-w-sm rounded-xl border border-red-200 dark:border-red-900 bg-red-50/90 dark:bg-red-950/50 shadow-sm text-center p-2">
              <div className="flex items-center justify-center gap-2">
                <span className="text-[10px] sm:text-xs font-bold text-red-700 dark:text-red-300 truncate">
                  Location Needed
                </span>
                <button
                  onClick={requestGPSLocation}
                  className="inline-flex items-center gap-1 rounded-full bg-red-600 hover:bg-red-700 text-white text-[10px] font-bold px-2.5 py-0.5 shadow-sm transition-colors cursor-pointer"
                >
                  <Crosshair className="h-2.5 w-2.5" />
                  GPS
                </button>
                <button
                  onClick={() => setShowLocationPicker(true)}
                  className="inline-flex items-center gap-1 rounded-full bg-white dark:bg-muted border border-border text-foreground text-[10px] font-bold px-2.5 py-0.5 shadow-sm hover:bg-muted transition-colors cursor-pointer"
                >
                  <MapPin className="h-2.5 w-2.5 text-primary" />
                  Pick Area
                </button>
              </div>
            </div>
          )}
        </div>

      </main>

      {/* 3. Bottom Region: Symptom Triage Box & Action (Docked directly at bottom of viewport) */}
      <footer className="flex-shrink-0 w-full px-4 pb-3 pt-2 bg-background/95 backdrop-blur-sm border-t border-border/40 z-10 max-w-lg mx-auto">
        <div className="w-full space-y-2">
          
          <p className="text-center text-[11px] sm:text-xs text-muted-foreground font-medium">
            Describe how you feel to get matched to the right hospitals
          </p>

          {/* Clean Compact Responsive Textarea */}
          <Textarea
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            placeholder="E.g. Person is choking / severe chest pain / high fever with shivering..."
            className="min-h-[52px] sm:min-h-[60px] max-h-[80px] w-full resize-none rounded-xl border-border/80 bg-muted/40 shadow-sm placeholder:text-muted-foreground/60 text-xs sm:text-sm focus-visible:ring-primary/20 py-2 px-3"
          />

          {/* Action Row */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              className="h-10 w-10 sm:h-11 sm:w-11 rounded-xl border-border/80 shadow-sm shrink-0 hover:bg-muted"
              aria-label="Voice input"
            >
              <Mic className="h-4 w-4 text-primary" />
            </Button>

            <Button
              onClick={analyzeSymptoms}
              disabled={isAnalyzing || !symptoms.trim()}
              className="flex-1 h-10 sm:h-11 rounded-xl bg-red-600 text-white font-bold text-xs sm:text-sm shadow-md hover:opacity-95 transition-all"
            >
              {isAnalyzing ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              )}
              {isAnalyzing ? "Analyzing symptoms..." : "Find hospitals"}
            </Button>
          </div>

          {hospitalError && (
            <p className="text-center text-[10px] sm:text-xs text-destructive font-medium line-clamp-1">
              {hospitalError}
            </p>
          )}

        </div>
      </footer>

      {/* LOCATION PICKER MODAL (For HTTP LAN testing or manual location selection) */}
      {showLocationPicker && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-end sm:items-center justify-center p-0 sm:p-4 animate-in fade-in duration-150">
          <div className="w-full sm:max-w-md bg-card border border-border rounded-t-3xl sm:rounded-2xl p-4 sm:p-5 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <div className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-primary" />
                <h3 className="text-sm sm:text-base font-bold text-foreground">Select Your Location</h3>
              </div>
              <button 
                onClick={() => setShowLocationPicker(false)}
                className="p-1 rounded-full hover:bg-muted text-muted-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Custom Search Box */}
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearchCustomLocation()}
                placeholder="Enter area, city or pincode..."
                className="flex-1 bg-muted/60 border border-border rounded-xl px-3 py-2 text-xs sm:text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              <button
                onClick={handleSearchCustomLocation}
                disabled={isSearchingLoc || !searchQuery.trim()}
                className="bg-primary text-primary-foreground font-bold text-xs px-3 py-2 rounded-xl flex items-center gap-1 shrink-0"
              >
                {isSearchingLoc ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                Search
              </button>
            </div>

            {/* Quick Pick Areas */}
            <div className="space-y-2">
              <p className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                Nearby Quick Select (Maharashtra & Metro)
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {PRESET_LOCATIONS.map((loc, i) => (
                  <button
                    key={i}
                    onClick={() => selectManualLocation(loc)}
                    className="flex items-center gap-2 p-2.5 rounded-xl border border-border bg-muted/30 hover:bg-primary/10 hover:border-primary/40 text-left transition-all cursor-pointer"
                  >
                    <MapPin className="h-4 w-4 text-primary shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold text-foreground truncate">{loc.name}</p>
                      <p className="text-[10px] text-muted-foreground">{loc.pincode}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Browser HTTP Note */}
            <div className="rounded-xl bg-muted/50 p-2.5 flex items-start gap-2 text-[10px] text-muted-foreground leading-relaxed">
              <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
              <span>
                <strong>Tip:</strong> Chrome and mobile browsers block hardware GPS over WiFi IP (<code className="text-foreground">http://192.168...</code>). Pick any area above to test all hospital matching and SOS functions.
              </span>
            </div>

          </div>
        </div>
      )}

      {/* SKELETON LOADING OVERLAY (DURING AI ANALYSIS) */}
      {isAnalyzing && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-md flex flex-col items-center justify-start p-4 sm:p-6 overflow-y-auto animate-in fade-in duration-200">
          <div className="w-full max-w-3xl space-y-4 my-auto pb-8">
            
            <div className="flex items-center justify-between rounded-2xl bg-card border border-border p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                  <HeartPulse className="h-5 w-5 animate-pulse text-red-500" />
                </div>
                <div>
                  <h3 className="text-xs sm:text-base font-bold text-foreground">
                    Analyzing Symptoms with Red Cross Triage...
                  </h3>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">
                    Matching clinical leaf protocols & calculating 50%+ hospital readiness
                  </p>
                </div>
              </div>
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
            </div>

            <div className="rounded-2xl border border-border bg-card p-4 sm:p-5 space-y-3 shadow-sm">
              <div className="flex items-center gap-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-4 w-36 rounded-md" />
              </div>
              <Skeleton className="h-4 w-full rounded-md" />
              <Skeleton className="h-4 w-4/5 rounded-md" />
            </div>

            <div className="rounded-2xl border border-border bg-card p-4 sm:p-5 space-y-3 shadow-sm">
              <div className="flex items-center gap-2">
                <Shield className="h-5 w-5 text-primary/40" />
                <Skeleton className="h-5 w-44 rounded-md" />
              </div>
              <div className="space-y-2 pt-2">
                <Skeleton className="h-9 w-full rounded-xl" />
                <Skeleton className="h-9 w-full rounded-xl" />
                <Skeleton className="h-9 w-full rounded-xl" />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Skeleton className="h-5 w-40 rounded-md" />
                <Skeleton className="h-4 w-24 rounded-md" />
              </div>
              <HospitalCardSkeleton />
            </div>

          </div>
        </div>
      )}

    </div>
  );
}

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — MedTour" },
      { name: "description", content: "Your travel-ready healthcare dashboard: SOS, AI symptom analysis and hospital recommendations." },
    ],
  }),
  component: Dashboard,
});
