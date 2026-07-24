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
  const operationEpochRef = useRef(0);
  const sessionEpochRef = useRef(0);

  const beginOperation = useCallback(() => {
    operationEpochRef.current += 1;
    return operationEpochRef.current;
  }, []);

  const isCurrentOperation = useCallback(
    (epoch: number) => operationEpochRef.current === epoch,
    [],
  );

  const updateSession = useCallback((next: CurrentSession | null) => {
    sessionEpochRef.current += 1;
    sessionRef.current = next;
    setSession(next);
    setStatus(next ? "authenticated" : "anonymous");
  }, []);

  const markAnonymous = useCallback(() => {
    beginOperation();
    updateSession(null);
  }, [beginOperation, updateSession]);

  const refresh = useCallback(async () => {
    const epoch = beginOperation();
    try {
      const next = await getCurrentSession();
      if (isCurrentOperation(epoch)) updateSession(next);
    } catch (reason) {
      if (!isCurrentOperation(epoch)) return;
      if (isAnonymousSessionError(reason)) {
        markAnonymous();
        return;
      }
      setStatus("unavailable");
      throw reason;
    }
  }, [beginOperation, isCurrentOperation, markAnonymous, updateSession]);

  const login = useCallback(
    async (accessCode: string) => {
      const epoch = beginOperation();
      const next = await createTeacherSession(accessCode);
      if (isCurrentOperation(epoch)) updateSession(next);
    },
    [beginOperation, isCurrentOperation, updateSession],
  );

  const logout = useCallback(async () => {
    const epoch = beginOperation();
    const current = sessionRef.current;
    if (current === null) {
      if (isCurrentOperation(epoch)) updateSession(null);
      return;
    }
    try {
      await deleteCurrentSession(current.csrf_token);
      if (isCurrentOperation(epoch)) updateSession(null);
    } catch (reason) {
      if (!isCurrentOperation(epoch)) return;
      if (isAnonymousSessionError(reason)) {
        markAnonymous();
        return;
      }
      throw reason;
    }
  }, [beginOperation, isCurrentOperation, markAnonymous, updateSession]);

  useEffect(() => {
    configureCsrfTokenProvider(() => sessionRef.current?.csrf_token);
    configureUnauthorizedHandler({
      captureEpoch: () => sessionEpochRef.current,
      invalidateIfCurrent: (epoch) => {
        if (epoch === sessionEpochRef.current) markAnonymous();
      },
    });
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
