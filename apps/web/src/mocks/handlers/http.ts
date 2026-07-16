import { HttpResponse, delay } from "msw";
import type { Meta } from "@/shared/api/types";
import { getDb, traceId } from "../db";

/** 匹配任意 origin 下的 /api/v2 前缀。 */
export const api = (path: string): string => `*/api/v2${path}`;

export function makeMeta(extra?: Partial<Meta>): Meta {
  return {
    trace_id: traceId(getDb()),
    server_time: new Date().toISOString(),
    ...extra,
  };
}

export function ok<T>(data: T, options?: { status?: number; meta?: Partial<Meta> }) {
  return HttpResponse.json(
    { ok: true, data, meta: makeMeta(options?.meta) },
    { status: options?.status ?? 200 },
  );
}

export function fail(
  status: number,
  code: string,
  message: string,
  options?: { retryable?: boolean; action?: string | null; details?: Record<string, unknown> },
) {
  return HttpResponse.json(
    {
      ok: false,
      error: {
        code,
        message,
        retryable: options?.retryable ?? false,
        action: options?.action ?? null,
        details: options?.details ?? {},
        trace_id: traceId(getDb()),
      },
    },
    { status },
  );
}

/** 会话校验；未登录返回 401 envelope。 */
export function guard(): ReturnType<typeof fail> | null {
  const db = getDb();
  if (!db.session) {
    return fail(401, "SESSION_EXPIRED", "登录已过期，请重新登录。", { action: "relogin" });
  }
  return null;
}

export function adminGuard(): ReturnType<typeof fail> | null {
  const unauth = guard();
  if (unauth) return unauth;
  const db = getDb();
  const role = db.session?.user.role;
  if (role !== "system_admin" && role !== "template_admin" && role !== "audit_admin") {
    return fail(403, "FORBIDDEN", "当前账号没有访问管理后台的权限。");
  }
  return null;
}

/** 模拟网络延迟（慢场景延长）。 */
export async function simulateLatency(slow = false): Promise<void> {
  const db = getDb();
  if (db.speedFactor < 0.3) return; // 测试环境跳过延迟
  await delay(slow ? 2600 : 120);
}

/** 游标分页：cursor 为起始下标字符串。 */
export function paginate<T>(items: T[], cursorRaw: string | null, pageSize: number): { page: T[]; nextCursor: string | null } {
  const start = cursorRaw ? Number.parseInt(cursorRaw, 10) || 0 : 0;
  const page = items.slice(start, start + pageSize);
  const nextCursor = start + pageSize < items.length ? String(start + pageSize) : null;
  return { page, nextCursor };
}
