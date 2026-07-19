import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/generated/api-schema";
import { apiConfig } from "@/shared/api/config";

export type ApiErrorBody = {
  error: {
    code: string;
    message: string;
    retryable: boolean;
    details?: Record<string, unknown>;
  };
  request_id: string;
};

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

type OpenApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

let csrfTokenProvider: CsrfTokenProvider | null = null;

/** Installs the CSRF token reader supplied by the real authentication bootstrap. */
export function configureCsrfTokenProvider(provider: CsrfTokenProvider | null) {
  csrfTokenProvider = provider;
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

const requestMiddleware: Middleware = {
  onRequest({ request }) {
    request.headers.set("Accept", "application/json");
    if (isWriteMethod(request.method) && !request.headers.has("X-CSRF-Token")) {
      const csrfToken = csrfTokenProvider?.()?.trim();
      if (csrfToken) request.headers.set("X-CSRF-Token", csrfToken);
    }
    return request;
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

apiClient.use(requestMiddleware);

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
