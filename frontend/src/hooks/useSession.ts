import { useCallback, useEffect, useRef, useState } from "react";

import {
  clearLocalSession,
  loadSession,
  loginSession,
  logoutSession,
} from "../lib/session";
import type { AuthContext } from "../lib/types";
import { useOnlineStatus } from "./useOnlineStatus";

export type SessionState = {
  context: AuthContext | null;
  loading: boolean;
  fromCache: boolean;
  error: string | null;
  online: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

export function useSession(): SessionState {
  const online = useOnlineStatus();
  const [context, setContext] = useState<AuthContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [fromCache, setFromCache] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const contextRef = useRef<AuthContext | null>(null);

  useEffect(() => {
    contextRef.current = context;
  }, [context]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const session = await loadSession();
      setContext(session?.context ?? null);
      setFromCache(session?.fromCache ?? false);
    } catch (loadError) {
      setContext(null);
      setFromCache(false);
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Impossible de charger la session.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const handleUnauthorized = () => {
      const hadSession = contextRef.current !== null;
      void clearLocalSession();
      setContext(null);
      setFromCache(false);
      if (hadSession) {
        setError("Ta session a expiré. Reconnecte-toi.");
      }
    };
    window.addEventListener("suivi:unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("suivi:unauthorized", handleUnauthorized);
    };
  }, []);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key !== "suivi.lastUserId") {
        return;
      }
      if (event.newValue === null) {
        void clearLocalSession();
        setContext(null);
        setError(null);
      } else if (event.newValue !== contextRef.current?.user.id) {
        void refresh();
      }
    };
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const logged = await loginSession(email, password);
      setContext(logged);
      setFromCache(false);
    } catch (loginError) {
      setError(
        loginError instanceof Error
          ? loginError.message
          : "Connexion impossible.",
      );
      throw loginError;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    setLoading(true);
    try {
      await logoutSession();
    } finally {
      setContext(null);
      setFromCache(false);
      setError(null);
      setLoading(false);
    }
  }, []);

  return {
    context,
    loading,
    fromCache,
    error,
    online,
    login,
    logout,
    refresh,
  };
}
