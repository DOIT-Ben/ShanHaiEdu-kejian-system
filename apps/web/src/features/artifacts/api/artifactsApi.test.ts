import { afterEach, describe, expect, it, vi } from "vitest";
import { listProjectArtifactsPage, startArtifactVersionQualityValidation } from "./artifactsApi";
import { configureCsrfTokenProvider } from "@/shared/api/client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

describe("R1 artifacts API", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("按 exact lesson 和类型读取产物并启动 exact 版本质量校验", async () => {
    configureCsrfTokenProvider(() => "csrf-r1-artifacts");
    const projectId = "01960000-0000-7000-8000-000000000001";
    const lessonId = "01960000-0000-7000-8000-000000000002";
    const versionId = "01960000-0000-7000-8000-000000000003";
    const artifact = {
      artifact_type: "lesson_plan",
      id: "01960000-0000-7000-8000-000000000004",
      lesson_unit_id: lessonId,
      project_id: projectId,
    };
    const accepted = {
      events_url: `/api/v2/projects/${projectId}/events/stream`,
      node_run_id: "01960000-0000-7000-8000-000000000005",
      status: "queued",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          data: { items: [artifact] },
          meta: { next_cursor: null },
          request_id: "request-artifacts",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ data: accepted, request_id: "request-quality" }, { status: 202 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listProjectArtifactsPage({
        artifactType: "lesson_plan",
        lessonId,
        limit: 10,
        projectId,
      }),
    ).resolves.toEqual({ items: [artifact], nextCursor: null });
    await expect(
      startArtifactVersionQualityValidation({
        artifactVersionId: versionId,
        idempotencyKey: `quality-${versionId}`,
      }),
    ).resolves.toEqual(accepted);

    const listUrl = new URL((fetchMock.mock.calls[0]?.[0] as Request).url);
    expect(listUrl.searchParams.get("lesson_id")).toBe(lessonId);
    expect(listUrl.searchParams.get("artifact_type")).toBe("lesson_plan");
    expect(listUrl.searchParams.get("page[limit]")).toBe("10");
    const qualityRequest = fetchMock.mock.calls[1]?.[0] as Request;
    expect(qualityRequest.url).toContain(`/artifact-versions/${versionId}/quality-validations`);
    expect(qualityRequest.headers.get("Idempotency-Key")).toBe(`quality-${versionId}`);
  });
});
