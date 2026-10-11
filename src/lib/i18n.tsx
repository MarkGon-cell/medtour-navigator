import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import en from "../i18n/en.json";
import hi from "../i18n/hi.json";

// Move translations to src/i18n for imports
type Dictionaries = Record<string, any>;

const dictionaries: Dictionaries = { en, hi };

type Language = "en" | "hi";
type TranslationKey = string;

interface I18nContextType {
  language: Language;
  t: (key: string, fallback?: string) => string;
  setLanguage: (lang: Language) => void;
}

const I18nContext = createContext<I18nContextType | null>(null);

// Flatten nested object into dot-notation keys
function getNestedValue(obj: any, path: string): string | undefined {
  return path.split(".").reduce((acc, part) => acc?.[part], obj);
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguage] = useState<Language>(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("i18n_language") as Language) || "en";
    }
    return "en";
  });

  const t = (key: string, fallback?: string): string => {
    const dict = dictionaries[language] || dictionaries.en;
    const value = getNestedValue(dict, key);
    if (typeof value === "string") return value;
    return fallback || key;
  };

  const handleSetLanguage = (lang: Language) => {
    setLanguage(lang);
    localStorage.setItem("i18n_language", lang);
  };

  useEffect(() => {
    const savedLang = localStorage.getItem("i18n_language") as Language | null;
    if (savedLang && dictionaries[savedLang]) {
      setLanguage(savedLang);
    }
  }, []);

  return (
    <I18nContext.Provider value={{ language, t, setLanguage: handleSetLanguage }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within an I18nProvider");
  }
  return ctx;
}

// Helper for deep translation lookup
export function deepTranslate(obj: any, t: (key: string, fallback?: string) => string): string {
  if (typeof obj === "string") {
    return t(obj);
  }
  return obj;
}
