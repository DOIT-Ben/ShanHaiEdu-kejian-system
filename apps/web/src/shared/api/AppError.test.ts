import { describe, expect, it } from "vitest";
import { AppError } from "./AppError";

function makeResponse(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers });
}

describe("AppError.fromResponse", () => {
  it("解析标准错误 Envelope", () => {
    const error = AppError.fromResponse(
      {
        ok: false,
        error: {
          code: "VERSION_CONFLICT",
          message: "内容已被修改",
          retryable: false,
          action: null,
          details: { server_row_version: 7 },
          trace_id: "tr_123",
        },
      },
      makeResponse(409),
    );
    expect(error.code).toBe("VERSION_CONFLICT");
    expect(error.status).toBe(409);
    expect(error.isConflict).toBe(true);
    expect(error.traceId).toBe("tr_123");
    expect((error.details as { server_row_version: number }).server_row_version).toBe(7);
  });

  it("非标准响应体回退为 HTTP 状态错误", () => {
    const error = AppError.fromResponse("<html>Bad Gateway</html>", makeResponse(502));
    expect(error.code).toBe("HTTP_502");
    expect(error.retryable).toBe(true);
    expect(error.message).toContain("服务暂时不可用");
  });

  it("401 视为会话过期", () => {
    const error = AppError.fromResponse(undefined, makeResponse(401));
    expect(error.isSessionExpired).toBe(true);
  });
});

describe("AppError.fromUnknown", () => {
  it("网络 TypeError → 可重试的 NETWORK_ERROR", () => {
    const error = AppError.fromUnknown(new TypeError("Failed to fetch"));
    expect(error.code).toBe("NETWORK_ERROR");
    expect(error.retryable).toBe(true);
  });
  it("AbortError → REQUEST_TIMEOUT", () => {
    const error = AppError.fromUnknown(new DOMException("aborted", "AbortError"));
    expect(error.code).toBe("REQUEST_TIMEOUT");
  });
  it("已是 AppError 时原样返回", () => {
    const original = new AppError({ code: "X", message: "x", status: 400 });
    expect(AppError.fromUnknown(original)).toBe(original);
  });
});
