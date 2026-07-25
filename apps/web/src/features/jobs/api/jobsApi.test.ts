import { afterEach, describe, expect, it, vi } from "vitest";
import { listProjectGenerationJobsPage } from "./jobsApi";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
}

describe("R1 jobs API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("使用 lesson_id 精确恢复项目中的生成任务", async () => {
    const projectId = "01960000-0000-7000-8000-000000000001";
    const lessonId = "01960000-0000-7000-8000-000000000002";
    const job = {
      created_at: "2026-07-25T00:00:00Z",
      id: "01960000-0000-7000-8000-000000000003",
      job_type: "workflow.node",
      lesson_unit_id: lessonId,
      progress_percent: 100,
      project_id: projectId,
      status: "succeeded",
      updated_at: "2026-07-25T00:01:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        data: { items: [job] },
        meta: { next_cursor: "jobs-next" },
        request_id: "request-jobs",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listProjectGenerationJobsPage({
        cursor: "jobs-cursor",
        lessonId,
        limit: 20,
        projectId,
      }),
    ).resolves.toEqual({ items: [job], nextCursor: "jobs-next" });

    const url = new URL((fetchMock.mock.calls[0]?.[0] as Request).url);
    expect(url.searchParams.get("lesson_id")).toBe(lessonId);
    expect(url.searchParams.get("page[cursor]")).toBe("jobs-cursor");
    expect(url.searchParams.get("page[limit]")).toBe("20");
  });
});
