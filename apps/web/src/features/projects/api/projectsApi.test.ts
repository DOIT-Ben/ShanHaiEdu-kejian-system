import { afterEach, describe, expect, it, vi } from "vitest";
import { createProject, getProjectVersioned, listProjectsPage } from "./projectsApi";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), {
    ...init,
    headers,
  });
}

describe("projectsApi", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("使用生成参数序列化分页查询", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        data: { items: [] },
        meta: { next_cursor: "next-1" },
        request_id: "req-list",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(listProjectsPage("cursor-1", 25)).resolves.toEqual({
      items: [],
      nextCursor: "next-1",
    });
    const url = new URL((fetchMock.mock.calls[0]?.[0] as Request).url);
    expect(url.searchParams.get("page[cursor]")).toBe("cursor-1");
    expect(url.searchParams.get("page[limit]")).toBe("25");
  });

  it("创建项目时发送类型化正文和幂等键", async () => {
    const project = {
      content_release_id: "01960000-0000-7000-8000-000000000003",
      created_at: "2026-07-20T00:00:00Z",
      execution_mode: "guided" as const,
      grade: "五年级",
      id: "01960000-0000-7000-8000-000000000001",
      knowledge_point: "百分数的意义",
      status: "draft" as const,
      subject: "primary_math" as const,
      textbook_edition: "人教版",
      title: "百分数",
      updated_at: "2026-07-20T00:00:00Z",
      workflow_definition_version_id: "01960000-0000-7000-8000-000000000004",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ data: project, request_id: "req-create" }, { status: 201 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      createProject({
        idempotencyKey: "create-project-1",
        input: { execution_mode: "guided", knowledge_point: "百分数的意义", title: "百分数" },
      }),
    ).resolves.toEqual(project);
    const request = fetchMock.mock.calls[0]?.[0] as Request;
    expect(request.headers.get("Idempotency-Key")).toBe("create-project-1");
    await expect(request.json()).resolves.toMatchObject({ execution_mode: "guided" });
  });

  it("读取项目时返回服务器 ETag", async () => {
    const project = {
      created_at: "2026-07-20T00:00:00Z",
      execution_mode: "guided" as const,
      id: "01960000-0000-7000-8000-000000000001",
      knowledge_point: "百分数的意义",
      status: "active" as const,
      subject: "primary_math" as const,
      title: "百分数",
      updated_at: "2026-07-20T00:00:00Z",
    };
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(
            { data: project, request_id: "req-project" },
            { headers: { ETag: '"project-v3"' } },
          ),
        ),
    );

    await expect(getProjectVersioned(project.id)).resolves.toEqual({
      etag: '"project-v3"',
      project,
    });
  });
});
