import type { ApiError } from "./types";

const statusFallbackMessage: Record<number, string> = {
  400: "请求内容不合法，请检查输入后重试。",
  401: "登录已过期，请重新登录。",
  403: "当前账号没有执行该操作的权限。",
  404: "请求的内容不存在或不可访问。",
  409: "内容已在其他位置被修改，需要处理版本冲突。",
  413: "文件超出允许的大小限制。",
  422: "部分字段未通过校验，请修正后重试。",
  429: "请求过于频繁，请稍后再试。",
};

function fallbackMessage(status: number): string {
  if (status in statusFallbackMessage) return statusFallbackMessage[status];
  if (status >= 500) return "服务暂时不可用，请稍后重试；问题持续请携带 Trace ID 联系管理员。";
  return "请求失败，请稍后重试。";
}

/**
 * 统一错误模型：由错误 Envelope（code/message/retryable/action/details/trace_id）
 * 与 HTTP 状态共同构成。页面据此展示教师语言错误与下一步动作。
 */
export class AppError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly action: string | null;
  readonly traceId: string | null;
  readonly details: unknown;

  constructor(input: {
    code: string;
    message: string;
    status: number;
    retryable?: boolean;
    action?: string | null;
    traceId?: string | null;
    details?: unknown;
  }) {
    super(input.message);
    this.name = "AppError";
    this.code = input.code;
    this.status = input.status;
    this.retryable = input.retryable ?? false;
    this.action = input.action ?? null;
    this.traceId = input.traceId ?? null;
    this.details = input.details;
  }

  /** 由错误 Envelope（可能缺失或非 JSON）与 Response 构造。 */
  static fromResponse(errorBody: unknown, response: Response): AppError {
    const envelope = errorBody as { ok?: boolean; error?: ApiError } | undefined;
    const err = envelope && envelope.ok === false ? envelope.error : undefined;
    if (err && typeof err.code === "string" && typeof err.message === "string") {
      return new AppError({
        code: err.code,
        message: err.message,
        status: response.status,
        retryable: err.retryable,
        action: err.action ?? null,
        traceId: err.trace_id ?? null,
        details: err.details,
      });
    }
    return new AppError({
      code: `HTTP_${response.status}`,
      message: fallbackMessage(response.status),
      status: response.status,
      retryable: response.status === 429 || response.status >= 500,
      traceId: response.headers.get("x-trace-id"),
    });
  }

  static fromUnknown(error: unknown): AppError {
    if (error instanceof AppError) return error;
    if (error instanceof DOMException && (error.name === "AbortError" || error.name === "TimeoutError")) {
      return new AppError({
        code: "REQUEST_TIMEOUT",
        message: "网络请求超时，已提交的生成任务不会因此中断，可稍后刷新查看。",
        status: 0,
        retryable: true,
      });
    }
    if (error instanceof TypeError) {
      return new AppError({
        code: "NETWORK_ERROR",
        message: "网络连接中断，请检查网络后重试；已提交的任务会继续在后台运行。",
        status: 0,
        retryable: true,
      });
    }
    return new AppError({
      code: "UNEXPECTED_ERROR",
      message: error instanceof Error ? error.message : "发生未预期的错误，请重试。",
      status: 0,
      retryable: false,
    });
  }

  /** 409 版本冲突。 */
  get isConflict(): boolean {
    return this.status === 409;
  }

  get isSessionExpired(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** 预算授权动作（生成前费用确认流）。 */
  get requiresBudgetAuthorization(): boolean {
    return this.action === "authorize_budget" || this.code === "BUDGET_AUTHORIZATION_REQUIRED";
  }

  /** 422 字段错误映射：details.field_errors -> { 字段: 提示 }。 */
  fieldErrors(): Record<string, string> {
    const details = this.details as { field_errors?: Record<string, string | string[]> } | undefined;
    const raw = details?.field_errors;
    if (!raw || typeof raw !== "object") return {};
    const out: Record<string, string> = {};
    for (const [field, value] of Object.entries(raw)) {
      out[field] = Array.isArray(value) ? value.join("；") : String(value);
    }
    return out;
  }

  /** 429 建议重试秒数。 */
  retryAfterSeconds(): number | null {
    const details = this.details as { retry_after_seconds?: number } | undefined;
    const value = details?.retry_after_seconds;
    return typeof value === "number" && value > 0 ? value : null;
  }
}
