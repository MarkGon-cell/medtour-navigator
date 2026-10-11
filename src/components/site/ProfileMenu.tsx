import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  ChevronDown,
  User as UserIcon,
  Upload,
  BookOpen,
} from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { QuickMedicalIdModal } from "@/components/site/QuickMedicalIdModal";

/**
 * Pill topbar profile menu:
 * Contains Upload Profile (Medical ID) and Learn More (Landing Page).
 */
export function ProfileMenu({ className = "" }: { className?: string }) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [medicalIdOpen, setMedicalIdOpen] = useState(false);

  return (
    <>
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={`flex items-center gap-1.5 rounded-full border border-border/60 bg-card/60 p-0.5 pr-1.5
                     transition-colors hover:bg-muted focus:outline-none focus-visible:ring-2 focus:ring-primary/40 ${className}`}
          aria-label="Open profile menu"
        >
          <Avatar className="h-7 w-7 ring-0">
            <AvatarFallback className="bg-primary text-primary-foreground text-[10px] font-bold">
              <UserIcon className="h-3.5 w-3.5" />
            </AvatarFallback>
          </Avatar>
          <ChevronDown className="h-3 w-3 text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56 rounded-2xl border-border/70 p-1.5 shadow-lg">
        {/* Upload Profile (Medical ID) */}
        <DropdownMenuItem
          className="cursor-pointer rounded-xl px-2.5 py-2.5 text-sm font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-2"
          onSelect={() => setMedicalIdOpen(true)}
        >
          <Upload className="h-4 w-4 text-primary" />
          <span>Upload Profile</span>
        </DropdownMenuItem>

        {/* Learn More (Landing Page) */}
        <DropdownMenuItem
          className="cursor-pointer rounded-xl px-2.5 py-2.5 text-sm font-semibold text-foreground hover:text-primary transition-colors flex items-center gap-2"
          onSelect={() => navigate({ to: "/landing" })}
        >
          <BookOpen className="h-4 w-4 text-primary" />
          <span>Learn More</span>
        </DropdownMenuItem>

        {/* Log Out / Clear Local Data */}
        <DropdownMenuItem
          className="cursor-pointer rounded-xl px-2.5 py-2.5 text-sm font-semibold text-destructive hover:bg-destructive/10 transition-colors flex items-center gap-2"
          onSelect={() => setMedicalIdOpen(true)}
        >
          <UserIcon className="h-4 w-4 text-destructive" />
          <span>Profile & Log Out</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>

    {/* Quick Medical ID / Profile Upload Modal */}
    <QuickMedicalIdModal isOpen={medicalIdOpen} onClose={() => setMedicalIdOpen(false)} />
    </>
  );
}
