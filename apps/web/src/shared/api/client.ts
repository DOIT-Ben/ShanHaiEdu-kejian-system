import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "@/generated/api-schema";
import { apiConfig } from "@/shared/api/config";

export type ApiErrorBody = components["schemas"]["error-envelope.schema"];

export class ApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly requestId: string;
  readonly details?: Record<string, unknown>;

  constructor(body: ApiErrorBody) {
    super(body.error.message);
    this.name = "ApiError";
    this.code = body.error.code;
    this.retryable = body.error.retryable;
    this.requestId = body.request_id;
    this.details = body.error.details;
  }
}

type CsrfTokenProvider = () => string | null | undefined;
type UnauthorizedHandler = () => void;

type OpenApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

let csrfTokenProvider: CsrfTokenProvider | null = null;
let unauthorizedHandler: UnauthorizedHandler | null = null;

/** Installs the CSRF token reader supplied by the real authentication bootstrap. */
export function configureCsrfTokenProvider(provider: CsrfTokenProvider | null) {
  csrfTokenProvider = provider;
}

export function configureUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
}

function readCsrfToken() {
  try {
    return csrfTokenProvider?.()?.trim() || undefined;
  } catch {
    return undefined;
  }
}

/** Reports bootstrap readiness without exposing the token value. */
export function isCsrfTokenAvailable() {
  return readCsrfToken() !== undefined;
}

export type ApiResponse<T> = {
  body: T;
  etag?: string;
};

function fallbackError(response: Response): ApiErrorBody {
  return {
    error: {
      code: `HTTP_${String(response.status)}`,
      message: `请求未完成，请稍后重试（${String(response.status)}）`,
      retryable: response.status >= 500,
    },
    request_id: response.headers.get("X-Request-ID") ?? "unknown",
  };
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ApiErrorBody>;
  return (
    typeof candidate.request_id === "string" &&
    Boolean(candidate.error) &&
    typeof candidate.error?.code === "string" &&
    typeof candidate.error.message === "string" &&
    typeof candidate.error.retryable === "boolean"
  );
}

function isApiSuccessBody(value: unknown): value is { data: unknown; request_id: string } {
  return (
    value !== null &&
    typeof value === "object" &&
    Object.hasOwn(value, "data") &&
    typeof (value as { request_id?: unknown }).request_id === "string"
  );
}

function invalidResponseError(response: Response) {
  return new ApiError({
    error: {
      code: "INVALID_API_RESPONSE",
      message: "服务返回了无法读取的内容，请稍后重试",
      retryable: true,
    },
    request_id: response.headers.get("X-Request-ID") ?? "unknown",
  });
}

function isWriteMethod(method: string) {
  const normalized = method.toUpperCase();
  return normalized !== "GET" && normalized !== "HEAD" && normalized !== "OPTIONS";
}

function isSessionBootstrapRequest(request: Request) {
  if (request.method.toUpperCase() !== "POST") return false;
  const baseUrl = new URL(resolveBaseUrl(apiConfig.baseUrl));
  const expectedPath = `${baseUrl.pathname.replace(/\/$/, "")}/auth/session`;
  const requestUrl = new URL(request.url);
  return requestUrl.origin === baseUrl.origin && requestUrl.pathname === expectedPath;
}

function csrfTokenUnavailableError() {
  return new ApiError({
    error: {
      code: "CSRF_TOKEN_UNAVAILABLE",
      message: "安全校验尚未就绪，请刷新页面后重试",
      retryable: false,
    },
    request_id: "client",
  });
}

function addCsrfToken(request: Request) {
  if (!isWriteMethod(request.method) || isSessionBootstrapRequest(request)) return;

  const suppliedToken = request.headers.get("X-CSRF-Token")?.trim();
  if (suppliedToken) {
    request.headers.set("X-CSRF-Token", suppliedToken);
    return;
  }

  const providerToken = readCsrfToken();
  if (providerToken) {
    request.headers.set("X-CSRF-Token", providerToken);
    return;
  }
  // Runtime/production writes must never fall back to a cookie-only request.
  if (import.meta.env.PROD || apiConfig.mode === "real") throw csrfTokenUnavailableError();
}

const requestMiddleware: Middleware = {
  onRequest({ request }) {
    request.headers.set("Accept", "application/json");
    addCsrfToken(request);
    return request;
  },
};

const responseMiddleware: Middleware = {
  onResponse({ response }) {
    if (response.status === 401) unauthorizedHandler?.();
    return response;
  },
};

async function authenticatedFetch(input: Request) {
  try {
    return await globalThis.fetch(input);
  } catch (reason) {
    if (reason instanceof DOMException && reason.name === "AbortError") throw reason;
    throw new ApiError({
      error: {
        code: "NETWORK_ERROR",
        message: "网络连接失败，请检查网络后重试",
        retryable: true,
      },
      request_id: "unknown",
    });
  }
}

function resolveBaseUrl(baseUrl: string) {
  if (!baseUrl.startsWith("/")) return baseUrl;
  return new URL(baseUrl, globalThis.location.origin).toString();
}

export const apiClient = createClient<paths>({
  baseUrl: resolveBaseUrl(apiConfig.baseUrl),
  credentials: "include",
  fetch: authenticatedFetch,
});

apiClient.use(requestMiddleware, responseMiddleware);

export function unwrapApiResult<T>(result: OpenApiResult<T>): T {
  if (!result.response.ok) {
    throw new ApiError(
      isApiErrorBody(result.error) ? result.error : fallbackError(result.response),
    );
  }
  if (result.data === undefined || !isApiSuccessBody(result.data)) {
    throw invalidResponseError(result.response);
  }
  return result.data;
}

export function unwrapApiResultWithResponse<T>(result: OpenApiResult<T>): ApiResponse<T> {
  return {
    body: unwrapApiResult(result),
    etag: result.response.headers.get("ETag") ?? undefined,
  };
}

export function unwrapEmptyApiResult(result: OpenApiResult<unknown>): void {
  if (!result.response.ok) {
    throw new ApiError(
      isApiErrorBody(result.error) ? result.error : fallbackError(result.response),
    );
  }
}
