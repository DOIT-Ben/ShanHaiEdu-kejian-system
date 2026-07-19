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

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  idempotent?: boolean;
  idempotencyKey?: string;
  etag?: string;
};

type CsrfTokenProvider = () => string | null | undefined;

let csrfTokenProvider: CsrfTokenProvider | null = null;

/**
 * Installs the token reader supplied by the real authentication bootstrap.
 * The API client never fetches, persists, or guesses a CSRF token itself.
 */
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

function isWriteMethod(method: string | undefined) {
  const normalized = (method ?? "GET").toUpperCase();
  return normalized !== "GET" && normalized !== "HEAD" && normalized !== "OPTIONS";
}

async function readJson<T>(response: Response): Promise<T | undefined> {
  const text = await response.text();
  if (!text.trim()) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

export async function apiRequestWithResponse<T>(
  path: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const { body: requestBody, etag, idempotencyKey, idempotent, ...requestInit } = options;
  const headers = new Headers(requestInit.headers);
  headers.set("Accept", "application/json");
  if (requestBody !== undefined) headers.set("Content-Type", "application/json");
  if (idempotencyKey) headers.set("Idempotency-Key", idempotencyKey);
  else if (idempotent) headers.set("Idempotency-Key", crypto.randomUUID());
  if (etag) headers.set("If-Match", etag);
  if (isWriteMethod(requestInit.method) && !headers.has("X-CSRF-Token")) {
    const csrfToken = csrfTokenProvider?.()?.trim();
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }

  let response: Response;
  try {
    response = await fetch(`${apiConfig.baseUrl}${path}`, {
      ...requestInit,
      body: requestBody === undefined ? undefined : JSON.stringify(requestBody),
      credentials: "include",
      headers,
    });
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

  if (!response.ok) {
    const body = await readJson<unknown>(response);
    throw new ApiError(isApiErrorBody(body) ? body : fallbackError(response));
  }
  const body = response.status === 204 ? (undefined as T) : await readJson<T>(response);
  if (response.status !== 204 && (body === undefined || !isApiSuccessBody(body))) {
    throw invalidResponseError(response);
  }
  return { body: body as T, etag: response.headers.get("ETag") ?? undefined };
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return (await apiRequestWithResponse<T>(path, options)).body;
}
