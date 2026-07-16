import { http } from "msw";
import { getDb, nextId } from "../db";
import { api, fail, ok, simulateLatency } from "./http";

/** Mock 内部：模拟 HttpOnly 会话 Cookie 在刷新后的续存（页面代码不可见）。 */
const SESSION_STORE_KEY = "__shanhai_mock_session_user__";

function persistSessionUserId(userId: string | null): void {
  if (typeof sessionStorage === "undefined") return;
  if (userId) sessionStorage.setItem(SESSION_STORE_KEY, userId);
  else sessionStorage.removeItem(SESSION_STORE_KEY);
}

export function restorePersistedSession(): void {
  if (typeof sessionStorage === "undefined") return;
  const db = getDb();
  const userId = sessionStorage.getItem(SESSION_STORE_KEY);
  if (!userId) return;
  const account = db.accounts.find((a) => a.user.user_id === userId);
  if (account) {
    db.session = { user: account.user, csrfToken: `csrf-${nextId(db, "tok")}` };
  }
}

export const authHandlers = [
  http.post(api("/auth/login"), async ({ request }) => {
    await simulateLatency();
    const db = getDb();
    const body = (await request.json()) as { identifier?: string; password?: string };
    if (db.flags.loginAlwaysFail) {
      return fail(401, "INVALID_CREDENTIALS", "账号或密码错误，请检查后重试。");
    }
    const account = db.accounts.find(
      (a) => (a.user.email === body.identifier || a.user.display_name === body.identifier) && a.password === body.password,
    );
    if (!account) {
      return fail(401, "INVALID_CREDENTIALS", "账号或密码错误，请检查后重试。");
    }
    db.session = { user: account.user, csrfToken: `csrf-${nextId(db, "tok")}` };
    persistSessionUserId(account.user.user_id);
    return ok({ user: account.user, csrf_token: db.session.csrfToken });
  }),

  http.get(api("/auth/me"), async () => {
    await simulateLatency();
    const db = getDb();
    if (db.flags.sessionExpiredOnFirstMe && !db.firstMeServed) {
      db.firstMeServed = true;
      db.session = null;
      persistSessionUserId(null);
      return fail(401, "SESSION_EXPIRED", "登录已过期，请重新登录。", { action: "relogin" });
    }
    if (!db.session) {
      return fail(401, "SESSION_EXPIRED", "登录已过期，请重新登录。", { action: "relogin" });
    }
    return ok({ user: db.session.user, csrf_token: db.session.csrfToken });
  }),

  http.post(api("/auth/logout"), async () => {
    const db = getDb();
    db.session = null;
    persistSessionUserId(null);
    return new Response(null, { status: 204 });
  }),
];
