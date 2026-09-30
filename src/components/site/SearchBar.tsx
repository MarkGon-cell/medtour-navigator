import { useEffect, useRef, useState } from "react";
import { Search, MapPin, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useNavigate } from "@tanstack/react-router";
import api from "@/lib/api";

type HospitalSearchResult = {
  id: number;
  name: string;
  city: string | null;
  state: string;
  district: string | null;
};

export function SearchBar({
  placeholder = "Search hospitals, specialties, cities…",
}: {
  placeholder?: string;
}) {
  const navigate = useNavigate();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<HospitalSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const searchRef = useRef<HTMLDivElement>(null);

  // Search automatically while typing
  useEffect(() => {
    const searchTerm = query.trim();

    if (!searchTerm) {
      setResults([]);
      setShowResults(false);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        setLoading(true);

        const response = await api.get<HospitalSearchResult[]>(
          "/hospitals/search",
          {
            params: {
              q: searchTerm,
            },
          }
        );

        console.log("Live search response:", response.data);

        setResults(response.data);
        setShowResults(true);
      } catch (error) {
        console.error("Hospital search failed:", error);
        setResults([]);
        setShowResults(true);
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [query]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      ) {
        setShowResults(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSearch = () => {
    if (!query.trim()) return;

    setShowResults(true);
  };

  const handleHospitalClick = (hospitalId: number) => {
    setQuery("");
    setResults([]);
    setShowResults(false);

    navigate({
      to: `/hospital-details/${hospitalId}`,
    });
  };

  return (
    <div
      ref={searchRef}
      className="relative flex w-full items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-soft"
    >
      <div className="flex flex-1 items-center gap-2 pl-2">
        <Search className="h-4 w-4 text-muted-foreground" />

        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (query.trim()) {
              setShowResults(true);
            }
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSearch();
            }
          }}
          placeholder={placeholder}
          className="border-0 bg-transparent shadow-none focus-visible:ring-0"
        />

        {loading && (
          <Loader2 className="mr-2 h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>

      <Button
        onClick={handleSearch}
        className="bg-gradient-hero text-white hover:opacity-95"
      >
        Search
      </Button>

      {/* Search Results */}
      {showResults && (
        <div className="absolute left-0 right-0 top-full z-[3000] mt-2 max-h-96 overflow-y-auto rounded-2xl border border-border bg-card p-2 shadow-lg">
          {loading && results.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              Searching hospitals...
            </div>
          ) : results.length > 0 ? (
            <div className="space-y-1">
              {results.map((hospital) => (
                <button
                  key={hospital.id}
                  type="button"
                  onClick={() => handleHospitalClick(hospital.id)}
                  className="flex w-full items-start gap-3 rounded-xl p-3 text-left transition-colors hover:bg-muted"
                >
                  <div className="mt-1 rounded-lg bg-primary/10 p-2">
                    <MapPin className="h-4 w-4 text-primary" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-foreground">
                      {hospital.name}
                    </p>

                    <p className="mt-1 text-sm text-muted-foreground">
                      {hospital.city || hospital.district || "Location not available"}
                      {hospital.state
                        ? `, ${hospital.state}`
                        : ""}
                    </p>
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="px-4 py-6 text-center">
              <p className="text-sm font-medium text-foreground">
                No hospitals found
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                Try a hospital name, city, district, or specialty.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}