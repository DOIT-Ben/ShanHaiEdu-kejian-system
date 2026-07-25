import { afterEach, describe, expect, it, vi } from "vitest";
import {
  prepareIntroOptionGeneration,
  prepareLessonDivision,
  prepareLessonPlanGeneration,
  startNodeRun,
} from "./workflowApi";
import { configureCsrfTokenProvider } from "@/shared/api/client";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    status,
  });
}

describe("R1 workflow API", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("准备三个 exact 节点并异步启动 NodeRun", async () => {
    configureCsrfTokenProvider(() => "csrf-r1-workflow");
    const projectId = "01960000-0000-7000-8000-000000000001";
    const lessonId = "01960000-0000-7000-8000-000000000002";
    const scopeVersionId = "01960000-0000-7000-8000-000000000003";
    const sourceIntroVersionId = "01960000-0000-7000-8000-000000000004";
    const nodes = [
      {
        id: "01960000-0000-7000-8000-000000000011",
        node_key: "lesson.division.generate",
        status: "ready",
      },
      {
        id: "01960000-0000-7000-8000-000000000012",
        node_key: "lesson_plan.generate",
        status: "ready",
      },
      {
        id: "01960000-0000-7000-8000-000000000013",
        node_key: "intro.generate_options",
        status: "ready",
      },
    ];
    const accepted = {
      events_url: "/api/v2/generation-jobs/01960000-0000-7000-8000-000000000020/events/stream",
      job_id: "01960000-0000-7000-8000-000000000020",
      status: "queued",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ data: nodes[0], request_id: "division" }))
      .mockResolvedValueOnce(jsonResponse({ data: nodes[1], request_id: "plan" }))
      .mockResolvedValueOnce(jsonResponse({ data: nodes[2], request_id: "intro" }))
      .mockResolvedValueOnce(jsonResponse({ data: accepted, request_id: "start" }, 202));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      prepareLessonDivision({
        idempotencyKey: "prepare-division-1",
        materialScopeArtifactVersionId: scopeVersionId,
        projectId,
      }),
    ).resolves.toEqual(nodes[0]);
    await expect(
      prepareLessonPlanGeneration({ idempotencyKey: "prepare-plan-1", lessonId }),
    ).resolves.toEqual(nodes[1]);
    await expect(
      prepareIntroOptionGeneration({
        generationMode: "refine_existing",
        idempotencyKey: "prepare-intro-1",
        lessonId,
        sourceArtifactVersionId: sourceIntroVersionId,
      }),
    ).resolves.toEqual(nodes[2]);
    await expect(
      startNodeRun({
        idempotencyKey: "start-node-run-1",
        nodeRunId: nodes[1]?.id ?? "",
        userRevision: "突出动手操作",
      }),
    ).resolves.toEqual(accepted);

    const divisionRequest = fetchMock.mock.calls[0]?.[0] as Request;
    await expect(divisionRequest.json()).resolves.toEqual({
      material_scope_artifact_version_id: scopeVersionId,
    });
    const introRequest = fetchMock.mock.calls[2]?.[0] as Request;
    await expect(introRequest.json()).resolves.toEqual({
      generation_mode: "refine_existing",
      source_artifact_version_id: sourceIntroVersionId,
    });
    const startRequest = fetchMock.mock.calls[3]?.[0] as Request;
    const introNode = nodes[1];
    if (!introNode) throw new Error("intro node fixture is missing");
    expect(startRequest.url).toContain(`/node-runs/${introNode.id}/start`);
    expect(startRequest.headers.get("Idempotency-Key")).toBe("start-node-run-1");
    await expect(startRequest.json()).resolves.toEqual({ user_revision: "突出动手操作" });
  });
});
