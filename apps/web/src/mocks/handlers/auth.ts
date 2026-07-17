import { http, HttpResponse } from "msw";
import { db } from "../db";
import { API, currentUser, fail, ok, requireSession, simulateLatency } from "../http";
import { persistMockSession } from "../session";

function userPayload(user: NonNullable<ReturnType<typeof currentUser>>) {
  return { user: { id: user.id, name: user.name, email: user.email, roles: user.roles } };
}

export const authHandlers = [
  http.post(API("/auth/login"), async ({ request }) => {
    await simulateLatency(200);
    const body = (await request.json()) as { email?: string; password?: string };
    const user = db.users.find((u) => u.email === body.email);
    if (!user || user.password !== body.password) {
      return fail(401, "INVALID_CREDENTIALS", "邮箱或密码不正确，请重试。");
    }
    db.sessionUserId = user.id;
    persistMockSession(user.id);
    return ok(userPayload(user));
  }),

  http.post(API("/auth/logout"), async () => {
    await simulateLatency(80);
    db.sessionUserId = null;
    persistMockSession(null);
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(API("/auth/me"), async () => {
    await simulateLatency(60);
    const denied = requireSession();
    if (denied) return denied;
    const user = currentUser()!;
    return ok(userPayload(user));
  }),
];
