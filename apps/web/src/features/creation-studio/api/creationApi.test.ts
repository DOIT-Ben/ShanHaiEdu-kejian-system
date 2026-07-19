import { afterEach, describe, expect, it, vi } from "vitest";
import { createCreationBatch, saveAdoptionToProject } from "./creationApi";

function response(data: unknown) {
  return new Response(JSON.stringify({ data, request_id: "request-1" }), {
    headers: { "Content-Type": "application/json" },
    status: 201,
  });
}

describe("creationApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("使用 project source 创建批次时不让客户端覆盖目标槽位", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        creation_package_id: "package-1",
        id: "batch-1",
        items: [],
        source: { project_id: "project-1", source_node_run_id: "node-1", workflow_run_id: "run-1" },
        source_kind: "project",
        status: "draft",
        studio_type: "image",
        title: "课堂图片",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await createCreationBatch({
      idempotencyKey: "batch-key",
      input: {
        creation_package_id: "package-1",
        source_kind: "project",
        studio_type: "image",
        title: "课堂图片",
      },
    });

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    await expect(request.json()).resolves.toEqual({
      creation_package_id: "package-1",
      source_kind: "project",
      studio_type: "image",
      title: "课堂图片",
    });
  });

  it("保存独立创作采用结果时要求显式目标项目与槽位", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      response({
        adoption_id: "adoption-1",
        binding_id: "binding-1",
        idempotent_replay: false,
        operation_id: "operation-1",
        status: "completed",
        target_project_id: "project-1",
        target_slot_key: "lesson.image",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await saveAdoptionToProject({
      adoptionId: "adoption-1",
      idempotencyKey: "save-key",
      input: {
        project_id: "project-1",
        replace_mode: "reject_if_occupied",
        slot_key: "lesson.image",
        source_kind: "standalone",
      },
    });

    const request = fetchMock.mock.calls[0]?.[0] as Request;
    await expect(request.json()).resolves.toMatchObject({
      project_id: "project-1",
      slot_key: "lesson.image",
      source_kind: "standalone",
    });
  });
});
