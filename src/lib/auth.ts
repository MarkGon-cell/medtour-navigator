import { useCallback, useEffect, useState } from "react";
import api from "@/lib/api";
import { setHistoryUser } from "@/lib/history";

export interface AuthUser {
  id?: number;
  email?: string;
  full_name?: string;
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return Boolean(localStorage.getItem("access_token"));
  } catch {
    return false;
  }
}

export function logout(): void {
  try {
    localStorage.removeItem("access_token");
  } catch {
    /* storage unavailable */
  }
  setHistoryUser(null);
}

/**
 * Lightweight auth state: tracks whether a token exists and resolves the
 * signed-in profile (name/email) when available.
 */
export function useAuth() {
  const [authenticated, setAuthenticated] = useState(isLoggedIn);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(isLoggedIn());

  const refresh = useCallback(async () => {
    const active = isLoggedIn();
    setAuthenticated(active);

    if (!active) {
      setUser(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await api.get("/profile");
      if (response.data?.id) {
        setUser({
          id: response.data.id,
          email: response.data.email,
          full_name: response.data.full_name,
        });
        setHistoryUser(response.data.id);
      }
    } catch (error) {
      console.error("Failed to load profile:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const signOut = useCallback(() => {
    logout();
    setAuthenticated(false);
    setUser(null);
  }, []);

  return { authenticated, user, loading, refresh, signOut };
}
