import { useSyncExternalStore } from "react";
import { apiConfig } from "@/shared/api/config";
import {
  MOCK_RUNTIME_STORAGE_KEY,
  mockRuntime,
  type MockRole,
  type MockSession,
} from "@/shared/api/mockClient";
import { developmentMockAccounts } from "@/shared/auth/mockCredentials.development";

export type { MockRole, MockSession };

/** Auth shares the runtime envelope so refreshes cannot produce split sessions. */
export const MOCK_AUTH_STORAGE_KEY = MOCK_RUNTIME_STORAGE_KEY;

export type SignInInput = {
  email: string;
  password: string;
  role?: MockRole;
};

export type MockAuthPolicyInput = {
  development: boolean;
  mode: string;
};

export function canUseMockAuth({ development, mode }: MockAuthPolicyInput) {
  return development && mode === "mock";
}

export const mockAuthEnabled = canUseMockAuth({
  development: import.meta.env.DEV,
  mode: apiConfig.mode,
});

export class MockAuthError extends Error {
  readonly code = "MOCK_INVALID_CREDENTIALS";

  constructor() {
    super("演示账号或密码不正确");
    this.name = "MockAuthError";
  }
}

export class MockAuthUnavailableError extends Error {
  readonly code = "MOCK_AUTH_DISABLED";

  constructor() {
    super("真实登录服务尚未接入，当前模式已停用演示登录。");
    this.name = "MockAuthUnavailableError";
  }
}

type AuthListener = () => void;

function id() {
  try {
    return globalThis.crypto.randomUUID();
  } catch {
    return `mock-session-${String(Date.now())}`;
  }
}

function accountFor(role: MockRole) {
  return developmentMockAccounts[role];
}

function normalizeInput(inputOrEmail: SignInInput | string, password?: string): SignInInput {
  return typeof inputOrEmail === "string"
    ? { email: inputOrEmail, password: password ?? "" }
    : inputOrEmail;
}

function inferRole(email: string, requestedRole?: MockRole): MockRole {
  if (requestedRole) return requestedRole;
  return email.toLowerCase().includes("admin") ? "admin" : "teacher";
}

function isActiveSession(session: MockSession, now: number) {
  const expiresAt = Date.parse(session.expires_at);
  return Number.isFinite(expiresAt) && expiresAt > now;
}

export function resolveMockSessionSnapshot(
  session: MockSession | null,
  enabled: boolean,
  now = Date.now(),
) {
  return enabled && session && isActiveSession(session, now) ? session : null;
}

export function getMockLoginDefaults() {
  if (!mockAuthEnabled) return { email: "", password: "" };
  const account = accountFor("teacher");
  return { email: account.email, password: account.password };
}

export function createMockSession(role: MockRole, email?: string): MockSession {
  if (!mockAuthEnabled) throw new MockAuthUnavailableError();
  const account = accountFor(role);
  const issuedAt = new Date().toISOString();
  return {
    id: id(),
    token: `demo-${role}-${id()}`,
    user: {
      id: `demo-${role}`,
      name: account.name,
      email: email ?? account.email,
      role,
    },
    issued_at: issuedAt,
    expires_at: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
  };
}

export const createDemoSession = createMockSession;

export function setMockSession(session: MockSession | null) {
  if (session && !mockAuthEnabled) throw new MockAuthUnavailableError();
  mockRuntime.setSession(session);
}

/** Pure snapshot reader: expiration never writes while React is rendering. */
export function getMockSession(): MockSession | null {
  return resolveMockSessionSnapshot(mockRuntime.getState().session, mockAuthEnabled);
}

export function signIn(input: SignInInput): MockSession;
export function signIn(email: string, password: string, role?: MockRole): MockSession;
export function signIn(
  inputOrEmail: SignInInput | string,
  password?: string,
  explicitRole?: MockRole,
): MockSession {
  if (!mockAuthEnabled) throw new MockAuthUnavailableError();
  const input = normalizeInput(inputOrEmail, password);
  const role = inferRole(input.email, input.role ?? explicitRole);
  const account = accountFor(role);
  if (input.email !== account.email || input.password !== account.password) {
    throw new MockAuthError();
  }
  const session = createMockSession(role, account.email);
  setMockSession(session);
  return session;
}

export function signInAsync(input: SignInInput): Promise<MockSession> {
  return Promise.resolve().then(() => signIn(input));
}

export function signOut() {
  setMockSession(null);
}

export function isMockAuthenticated() {
  return getMockSession() !== null;
}

export function hasMockRole(role: MockRole) {
  return getMockSession()?.user.role === role;
}

export function subscribeMockAuth(listener: AuthListener) {
  return mockRuntime.subscribe(listener);
}

export function useMockSession() {
  return useSyncExternalStore(subscribeMockAuth, getMockSession, getMockSession);
}

export function useMockAuth() {
  const session = useMockSession();
  return {
    session,
    user: session?.user ?? null,
    isAuthenticated: session !== null,
    isTeacher: session?.user.role === "teacher",
    isAdmin: session?.user.role === "admin",
    signIn,
    signOut,
  };
}
