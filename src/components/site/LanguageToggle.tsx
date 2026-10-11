import { Languages } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

interface LanguageToggleProps {
  variant?: "default" | "compact";
  className?: string;
}

export function LanguageToggle({ variant = "default", className }: LanguageToggleProps) {
  const { language, setLanguage } = useI18n();

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border border-border bg-muted/40 p-1 text-xs font-medium",
        variant === "compact" ? "h-7 gap-1 px-1.5" : "h-8 gap-2 px-2",
        className
      )}
    >
      <Languages className="h-3 w-3 text-muted-foreground" />
      <button
        onClick={() => setLanguage("en")}
        className={cn(
          "rounded-full px-1.5 py-0.5 transition-all",
          language === "en"
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        EN
      </button>
      <button
        onClick={() => setLanguage("hi")}
        className={cn(
          "rounded-full px-1.5 py-0.5 transition-all",
          language === "hi"
            ? "bg-primary text-primary-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground"
        )}
      >
        हिं
      </button>
    </div>
  );
}
