import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function SearchBar({ placeholder = "Search hospitals, specialties, cities…" }: { placeholder?: string }) {
  return (
    <div className="flex w-full items-center gap-2 rounded-2xl border border-border bg-card p-2 shadow-soft">
      <div className="flex flex-1 items-center gap-2 pl-2">
        <Search className="h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={placeholder}
          className="border-0 bg-transparent shadow-none focus-visible:ring-0"
        />
      </div>
      <Button className="bg-gradient-hero text-white hover:opacity-95">Search</Button>
    </div>
  );
}
