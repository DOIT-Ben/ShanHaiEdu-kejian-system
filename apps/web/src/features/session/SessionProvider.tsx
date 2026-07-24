import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import {
  createTeacherSession,
  deleteCurrentSession,
  getCurrentSession,
  type CurrentSession,
} from "@/features/session/api/sessionApi";
import {
  ApiError,
  configureCsrfTokenProvider,
  configureUnauthorizedHandler,
} from "@/shared/api/client";

type SessionStatus = "loading" | "authenticated" | "anonymous" | "unavailable";

type SessionContextValue = {
  session: CurrentSession | null;
  status: SessionStatus;
  login: (accessCode: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const SessionContext = createContext<SessionContextValue | null>(null);

function isAnonymousSessionError(reason: unknown) {
  return reason instanceof ApiError && reason.code === "AUTHENTICATION_REQUIRED";
}

export function SessionProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<CurrentSession | null>(null);
  const [status, setStatus] = useState<SessionStatus>("loading");
  const sessionRef = useRef<CurrentSession | null>(null);

  const updateSession = useCallback((next: CurrentSession | null) => {
    sessionRef.current = next;
    setSession(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  const markAnonymous = useCallback(() => updateSession(null), [updateSession]);

  const refresh = useCallback(async () => {
    try {
      updateSession(await getCurrentSession());
    } catch (reason) {
      if (isAnonymousSessionError(reason)) {
        markAnonymous();
        return;
      }
      setStatus("unavailable");
      throw reason;
    }
  }, [markAnonymous, updateSession]);

  const login = useCallback(
    async (accessCode: string) => updateSession(await createTeacherSession(accessCode)),
    [updateSession],
  );

  const logout = useCallback(async () => {
    const current = sessionRef.current;
    if (current === null) {
      markAnonymous();
      return;
    }
    try {
      await deleteCurrentSession(current.csrf_token);
      markAnonymous();
    } catch (reason) {
      if (isAnonymousSessionError(reason)) {
        markAnonymous();
        return;
      }
      throw reason;
    }
  }, [markAnonymous]);

  useEffect(() => {
    configureCsrfTokenProvider(() => sessionRef.current?.csrf_token);
    configureUnauthorizedHandler(markAnonymous);
    void refresh().catch(() => undefined);
    return () => {
      configureCsrfTokenProvider(null);
      configureUnauthorizedHandler(null);
    };
  }, [markAnonymous, refresh]);

  const value = useMemo<SessionContextValue>(
    () => ({ login, logout, refresh, session, status }),
    [login, logout, refresh, session, status],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const context = useContext(SessionContext);
  if (context === null) throw new Error("useSession must be used inside SessionProvider");
  return context;
}
