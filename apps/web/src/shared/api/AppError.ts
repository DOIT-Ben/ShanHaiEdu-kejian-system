/**
 * 统一错误模型（contracts/error-envelope.schema.json）：
 * { error: { code, message, retryable, details? }, request_id }
 * 页面据此展示教师语言错误、Request ID 与下一步动作。
 */

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
  if (status >= 500) return "服务暂时不可用，请稍后重试；问题持续请携带请求编号联系管理员。";
  return "请求失败，请稍后重试。";
}

interface ErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    retryable?: unknown;
    details?: unknown;
  };
  request_id?: unknown;
}

export class AppError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly requestId: string | null;
  readonly details: Record<string, unknown>;

  constructor(input: {
    code: string;
    message: string;
    status: number;
    retryable?: boolean;
    requestId?: string | null;
    details?: Record<string, unknown>;
  }) {
    super(input.message);
    this.name = "AppError";
    this.code = input.code;
    this.status = input.status;
    this.retryable = input.retryable ?? false;
    this.requestId = input.requestId ?? null;
    this.details = input.details ?? {};
  }

  /** 由错误 Envelope（可能缺失或非 JSON）与 Response 构造。 */
  static fromResponse(errorBody: unknown, response: Response): AppError {
    const envelope = (errorBody ?? {}) as ErrorEnvelope;
    const err = envelope.error;
    if (err && typeof err.code === "string" && typeof err.message === "string") {
      return new AppError({
        code: err.code,
        message: err.message,
        status: response.status,
        retryable: typeof err.retryable === "boolean" ? err.retryable : false,
        requestId: typeof envelope.request_id === "string" ? envelope.request_id : null,
        details:
          err.details && typeof err.details === "object"
            ? (err.details as Record<string, unknown>)
            : {},
      });
    }
    return new AppError({
      code: `HTTP_${response.status}`,
      message: fallbackMessage(response.status),
      status: response.status,
      retryable: response.status === 429 || response.status >= 500,
      requestId: response.headers.get("x-request-id"),
    });
  }

  static fromUnknown(error: unknown): AppError {
    if (error instanceof AppError) return error;
    if (
      error instanceof DOMException &&
      (error.name === "AbortError" || error.name === "TimeoutError")
    ) {
      return new AppError({
        code: "REQUEST_TIMEOUT",
        message: "网络请求超时。已提交的生成任务不会因此中断，可稍后刷新查看。",
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

  /** 409：ETag 版本冲突或幂等键冲突。 */
  get isConflict(): boolean {
    return this.status === 409;
  }

  /** 409 EDIT_CONFLICT：需要弹出冲突处理对话框。 */
  get isEditConflict(): boolean {
    return this.status === 409 && this.code === "EDIT_CONFLICT";
  }

  get isSessionExpired(): boolean {
    return this.status === 401;
  }

  get isForbidden(): boolean {
    return this.status === 403;
  }

  /** 保存到项目时目标单值槽位已占用（save_conflict 场景）。 */
  get isSlotOccupied(): boolean {
    return this.status === 409 && this.code === "SLOT_OCCUPIED";
  }

  /** 全自动预算确认（budget_pause 场景）。 */
  get requiresBudgetAuthorization(): boolean {
    return this.code === "BUDGET_AUTHORIZATION_REQUIRED";
  }

  /** 422 字段错误映射：details.field_errors -> { 字段: 提示 }。 */
  fieldErrors(): Record<string, string> {
    const raw = this.details["field_errors"];
    if (!raw || typeof raw !== "object") return {};
    const out: Record<string, string> = {};
    for (const [field, value] of Object.entries(raw as Record<string, unknown>)) {
      out[field] = Array.isArray(value) ? value.join("；") : String(value);
    }
    return out;
  }

  /** 429 建议重试秒数。 */
  retryAfterSeconds(): number | null {
    const value = this.details["retry_after_seconds"];
    return typeof value === "number" && value > 0 ? value : null;
  }
}
