import { HttpResponse } from "msw";
import { db, nextRequestId, makeEtag } from "./db";

/**
 * Mock HTTP 帮助层：统一信封（{data, meta?, request_id}）、错误包、
 * 幂等键与 If-Match 校验（contracts/api-conventions.md）。
 */

export function ok<T>(data: T, init?: { meta?: Record<string, unknown>; etag?: number; status?: number }): Response {
  const headers: Record<string, string> = {};
  if (init?.etag !== undefined) headers["ETag"] = makeEtag(init.etag);
  return HttpResponse.json(
    { data, ...(init?.meta ? { meta: init.meta } : {}), request_id: nextRequestId() },
    { status: init?.status ?? 200, headers },
  );
}

export function fail(
  status: number,
  code: string,
  message: string,
  options?: { retryable?: boolean; details?: Record<string, unknown> },
): Response {
  return HttpResponse.json(
    {
      error: {
        code,
        message,
        retryable: options?.retryable ?? false,
        ...(options?.details ? { details: options.details } : {}),
      },
      request_id: nextRequestId(),
    },
    { status },
  );
}

export function notFound(what = "资源"): Response {
  return fail(404, "NOT_FOUND", `${what}不存在或不可访问。`);
}

export function unauthorized(): Response {
  return fail(401, "UNAUTHENTICATED", "登录已过期，请重新登录。");
}

export function forbidden(): Response {
  return fail(403, "FORBIDDEN", "当前账号没有执行该操作的权限。");
}

/** 幂等键：必填 8–128 字符；同键同摘要重放原结果；同键不同摘要 409。 */
export function checkIdempotency(
  request: Request,
  digest: string,
): { replay: Response } | { store: (body: unknown, status: number) => void } | { error: Response } {
  const key = request.headers.get("Idempotency-Key");
  if (!key || key.length < 8 || key.length > 128) {
    return { error: fail(400, "IDEMPOTENCY_KEY_REQUIRED", "缺少有效的 Idempotency-Key 请求头。") };
  }
  const prior = db.idempotency.get(key);
  if (prior) {
    if (prior.digest !== digest) {
      return { error: fail(409, "IDEMPOTENCY_CONFLICT", "同一幂等键被用于不同请求。") };
    }
    return {
      replay: HttpResponse.json(prior.body as Record<string, unknown>, { status: prior.status }),
    };
  }
  return {
    store: (body: unknown, status: number) => {
      db.idempotency.set(key, { digest, body, status });
    },
  };
}

/** 便捷封装：幂等 + 构造响应一次完成。 */
export function idempotent(
  request: Request,
  digest: string,
  produce: () => { data: unknown; status?: number; etag?: number } | Response,
): Response {
  const check = checkIdempotency(request, digest);
  if ("error" in check) return check.error;
  if ("replay" in check) return check.replay;
  const outcome = produce();
  if (outcome instanceof Response) return outcome;
  const status = outcome.status ?? 200;
  const body = { data: outcome.data, request_id: nextRequestId() };
  check.store(body, status);
  const headers: Record<string, string> = {};
  if (outcome.etag !== undefined) headers["ETag"] = makeEtag(outcome.etag);
  return HttpResponse.json(body, { status, headers });
}

/** If-Match 校验：缺失 428，不匹配 409 EDIT_CONFLICT。 */
export function checkIfMatch(request: Request, currentEtagCounter: number): Response | null {
  const ifMatch = request.headers.get("If-Match");
  if (!ifMatch) {
    return fail(428, "PRECONDITION_REQUIRED", "更新可编辑内容必须携带 If-Match。");
  }
  // RFC 9110：If-Match: * 匹配任意当前版本（列表型资源无单独 GET 时使用）
  if (ifMatch === "*") return null;
  if (ifMatch !== makeEtag(currentEtagCounter)) {
    return fail(409, "EDIT_CONFLICT", "内容已在其他位置被修改，请刷新后基于最新版本继续。", {
      details: { current_etag: makeEtag(currentEtagCounter) },
    });
  }
  return null;
}

export function requireSession(): Response | null {
  if (!db.sessionUserId) return unauthorized();
  return null;
}

export function requireAdmin(): Response | null {
  const denied = requireSession();
  if (denied) return denied;
  const user = db.users.find((u) => u.id === db.sessionUserId);
  if (!user) return unauthorized();
  const isAdmin = user.roles.some((r) => r !== "teacher");
  if (!isAdmin) return forbidden();
  return null;
}

export function currentUser() {
  return db.users.find((u) => u.id === db.sessionUserId) ?? null;
}

/** 模拟网络延迟；speedFactor<0.3（测试）时跳过。 */
export async function simulateLatency(ms = 120): Promise<void> {
  if (db.speedFactor < 0.3) return;
  await new Promise((resolve) => setTimeout(resolve, ms * db.speedFactor));
}

export const API = (path: string): string => `*/api/v2${path}`;
