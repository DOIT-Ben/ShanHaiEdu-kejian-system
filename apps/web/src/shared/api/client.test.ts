import { afterEach, describe, expect, it, vi } from "vitest";
import {
  apiRequest,
  apiRequestWithResponse,
  configureCsrfTokenProvider,
} from "@/shared/api/client";

describe("apiRequest", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("保留调用方提供的幂等键并返回 ETag", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { id: "project-1" }, request_id: "req-1" }), {
        headers: { "Content-Type": "application/json", ETag: '"project-v3"' },
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await apiRequestWithResponse<{ data: { id: string } }>("/projects/project-1", {
      idempotencyKey: "create-project-1",
      method: "PATCH",
      body: { title: "认识百分数" },
    });

    const request = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(request.headers).get("Idempotency-Key")).toBe("create-project-1");
    expect(response.etag).toBe('"project-v3"');
    expect(response.body.data.id).toBe("project-1");
  });

  it("将非 JSON 错误安全转换为标准错误", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("Bad Gateway", {
          headers: { "X-Request-ID": "req-gateway" },
          status: 502,
        }),
      ),
    );

    await expect(apiRequest("/projects")).rejects.toMatchObject({
      code: "HTTP_502",
      requestId: "req-gateway",
      retryable: true,
    });
  });

  it("拒绝成功状态下不可解析的响应", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("not-json", {
          headers: { "X-Request-ID": "req-invalid" },
          status: 200,
        }),
      ),
    );

    await expect(apiRequest("/projects")).rejects.toMatchObject({
      code: "INVALID_API_RESPONSE",
      requestId: "req-invalid",
    });
  });

  it("拒绝缺少 data 或 request_id 的成功响应 envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ items: [] }), {
          headers: { "X-Request-ID": "req-shape" },
          status: 200,
        }),
      ),
    );

    await expect(apiRequest("/projects")).rejects.toMatchObject({
      code: "INVALID_API_RESPONSE",
      requestId: "req-shape",
    });
  });

  it("将网络失败转换为可重试的标准错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiRequest("/projects")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      retryable: true,
    });
  });

  it("保留 AbortError 供调用方识别主动取消", async () => {
    const aborted = new DOMException("The operation was aborted", "AbortError");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(aborted));

    await expect(apiRequest("/projects")).rejects.toBe(aborted);
  });

  it("只在写请求中注入调用方提供的 CSRF token", async () => {
    configureCsrfTokenProvider(() => "csrf-token-from-bootstrap");
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(
          new Response(JSON.stringify({ data: {}, request_id: "req-csrf" }), { status: 200 }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/projects/project-1", { body: { title: "更新" }, method: "PATCH" });
    await apiRequest("/projects/project-1", { method: "GET" });

    const writeHeaders = new Headers((fetchMock.mock.calls[0]?.[1] as RequestInit).headers);
    const readHeaders = new Headers((fetchMock.mock.calls[1]?.[1] as RequestInit).headers);
    expect(writeHeaders.get("X-CSRF-Token")).toBe("csrf-token-from-bootstrap");
    expect(readHeaders.has("X-CSRF-Token")).toBe(false);
  });
});
