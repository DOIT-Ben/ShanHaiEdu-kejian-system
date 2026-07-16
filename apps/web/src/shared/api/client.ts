import createClient from "openapi-fetch";
import type { paths } from "./generated";
import { env } from "@/shared/config/env";
import { AppError } from "./AppError";
import type { Meta } from "./types";

/**
 * CSRF Token 只保存在内存中（由当前会话响应提供），
 * 不进入 localStorage / sessionStorage。
 */
let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

export const SESSION_EXPIRED_EVENT = "shanhai:session-expired";

function notifySessionExpired(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const DEFAULT_TIMEOUT_MS = 30_000;

function combineSignals(a: AbortSignal | null | undefined, b: AbortSignal): AbortSignal {
  if (!a) return b;
  if (typeof AbortSignal.any === "function") return AbortSignal.any([a, b]);
  return a;
}

/** 默认 30s 超时；调用方可传入自己的 signal 参与竞争。 */
const timeoutFetch: typeof fetch = async (input, init) => {
  const request = input instanceof Request ? input : new Request(input, init);
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(new DOMException("请求超时", "TimeoutError")),
    DEFAULT_TIMEOUT_MS,
  );
  try {
    const signal = combineSignals(request.signal, controller.signal);
    return await fetch(new Request(request, { signal }));
  } finally {
    clearTimeout(timer);
  }
};

export const client = createClient<paths>({
  baseUrl: env.apiBaseUrl,
  credentials: "include",
  fetch: timeoutFetch,
});

client.use({
  onRequest({ request }) {
    request.headers.set("X-Requested-With", "shanhai-web");
    request.headers.set("X-Client-Version", env.buildVersion);
    if (MUTATING_METHODS.has(request.method) && csrfToken) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
  },
});

export interface ApiResult<T> {
  data: T;
  meta: Meta;
}

interface RawResult<T> {
  data?: { ok: true; data: T; meta: Meta };
  error?: unknown;
  response: Response;
}

/**
 * 解包统一响应 Envelope；失败时抛出 AppError。
 * 401 会广播会话过期事件，由应用层清理缓存并跳转登录。
 */
export function unwrap<T>(result: RawResult<T>): ApiResult<T> {
  const { data, error, response } = result;
  if (error !== undefined || !data) {
    const appError = AppError.fromResponse(error, response);
    if (appError.isSessionExpired) notifySessionExpired();
    throw appError;
  }
  return { data: data.data, meta: data.meta };
}

/** 解包无响应体（204）的请求。 */
export function unwrapVoid(result: { error?: unknown; response: Response }): void {
  const { error, response } = result;
  if (!response.ok) {
    const appError = AppError.fromResponse(error, response);
    if (appError.isSessionExpired) notifySessionExpired();
    throw appError;
  }
}
