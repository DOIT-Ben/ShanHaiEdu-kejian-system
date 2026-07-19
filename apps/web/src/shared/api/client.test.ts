import { afterEach, describe, expect, it, vi } from "vitest";
import {
  apiClient,
  configureCsrfTokenProvider,
  unwrapApiResult,
  unwrapApiResultWithResponse,
} from "@/shared/api/client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
}

describe("typed api client", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("保留 credentials、幂等键、If-Match、CSRF 与 ETag", async () => {
    configureCsrfTokenProvider(() => "csrf-token-from-bootstrap");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          data: {
            mode: "guided",
            node_rules: [],
            policy_version: 2,
            project_id: "01960000-0000-7000-8000-000000000001",
            updated_at: "2026-07-20T00:00:00Z",
            workflow_definition_version_id: "01960000-0000-7000-8000-000000000002",
          },
          request_id: "req-policy",
        },
        { headers: { ETag: '"policy-v2"' }, status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiClient.PATCH("/projects/{project_id}/automation-policy", {
      body: { mode: "guided" },
      params: {
        header: { "Idempotency-Key": "policy-update-1", "If-Match": '"policy-v1"' },
        path: { project_id: "01960000-0000-7000-8000-000000000001" },
      },
    });
    const response = unwrapApiResultWithResponse(result);

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.credentials).toBe("include");
    expect(request.headers.get("Idempotency-Key")).toBe("policy-update-1");
    expect(request.headers.get("If-Match")).toBe('"policy-v1"');
    expect(request.headers.get("X-CSRF-Token")).toBe("csrf-token-from-bootstrap");
    expect(response.etag).toBe('"policy-v2"');
  });

  it("不会向读取请求注入 CSRF token", async () => {
    configureCsrfTokenProvider(() => "csrf-token-from-bootstrap");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ data: { items: [] }, meta: { next_cursor: null }, request_id: "req-list" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    unwrapApiResult(await apiClient.GET("/projects"));

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.has("X-CSRF-Token")).toBe(false);
  });

  it("将标准与非标准 HTTP 错误转换为 ApiError", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            error: { code: "EDIT_CONFLICT", message: "版本已变化", retryable: false },
            request_id: "req-conflict",
          },
          { status: 409 },
        ),
      )
      .mockResolvedValueOnce(
        new Response("Bad Gateway", {
          headers: { "X-Request-ID": "req-gateway" },
          status: 502,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      apiClient
        .GET("/projects/{project_id}", {
          params: { path: { project_id: "01960000-0000-7000-8000-000000000001" } },
        })
        .then(unwrapApiResult),
    ).rejects.toMatchObject({ code: "EDIT_CONFLICT", requestId: "req-conflict" });
    await expect(apiClient.GET("/projects").then(unwrapApiResult)).rejects.toMatchObject({
      code: "HTTP_502",
      requestId: "req-gateway",
      retryable: true,
    });
  });

  it("将网络失败转换为可重试错误并保留 AbortError", async () => {
    const aborted = new DOMException("The operation was aborted", "AbortError");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockRejectedValueOnce(new TypeError("Failed to fetch"))
        .mockRejectedValueOnce(aborted),
    );

    await expect(apiClient.GET("/projects")).rejects.toMatchObject({
      code: "NETWORK_ERROR",
      retryable: true,
    });
    await expect(apiClient.GET("/projects")).rejects.toBe(aborted);
  });
});
