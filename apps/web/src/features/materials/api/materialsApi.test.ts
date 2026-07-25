import { afterEach, describe, expect, it, vi } from "vitest";
import {
  confirmMaterialUpload,
  createMaterialScopeVersion,
  createMaterialUploadSession,
  listProjectMaterialsPage,
  sha256File,
  uploadMaterialFile,
} from "./materialsApi";
import { configureCsrfTokenProvider } from "@/shared/api/client";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

describe("materialsApi", () => {
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.unstubAllGlobals();
  });

  it("计算稳定摘要并完成创建会话、直传、确认三段流程", async () => {
    const file = new File(["hello"], "lesson.pdf", { type: "application/pdf" });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            data: {
              expires_at: "2026-07-20T02:00:00Z",
              material_id: "material-1",
              method: "PUT",
              required_headers: { "Content-Type": "application/pdf" },
              upload_session_id: "upload-1",
              upload_url: "https://storage.example.test/upload-1",
            },
            request_id: "request-session",
          },
          { status: 201 },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { headers: { ETag: '"etag-1"' }, status: 200 }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            data: {
              events_url: "/api/v2/generation-jobs/job-1/events/stream",
              job_id: "job-1",
              status: "queued",
            },
            request_id: "request-confirm",
          },
          { status: 202 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(sha256File(file)).resolves.toBe(
      "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
    );
    const session = await createMaterialUploadSession({
      idempotencyKey: "session-key",
      input: {
        filename: file.name,
        media_type: file.type,
        sha256: "sha-1",
        size_bytes: file.size,
      },
      projectId: "project-1",
    });
    const etag = await uploadMaterialFile(session, file);
    const job = await confirmMaterialUpload({
      etag,
      file,
      idempotencyKey: "confirm-key",
      materialId: session.material_id,
      projectId: "project-1",
      sha256: "sha-1",
      uploadSessionId: session.upload_session_id,
    });

    expect(job.job_id).toBe("job-1");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).method).toBe("PUT");
    expect((fetchMock.mock.calls[1]?.[1] as RequestInit).headers).toEqual({
      "Content-Type": "application/pdf",
    });
    const confirmRequest = fetchMock.mock.calls[2]?.[0] as Request;
    await expect(confirmRequest.json()).resolves.toMatchObject({
      etag: '"etag-1"',
      upload_session_id: "upload-1",
    });
  });

  it("按项目分页读取教材并创建 exact 教材范围版本", async () => {
    configureCsrfTokenProvider(() => "csrf-r1-materials");
    const material = {
      confirmed_at: "2026-07-25T00:00:00Z",
      created_at: "2026-07-25T00:00:00Z",
      file_asset_id: "01960000-0000-7000-8000-000000000003",
      id: "01960000-0000-7000-8000-000000000002",
      material_kind: "textbook",
      mime_type: "application/pdf",
      original_filename: "教材.pdf",
      project_id: "01960000-0000-7000-8000-000000000001",
      updated_at: "2026-07-25T00:00:00Z",
      upload_status: "confirmed" as const,
    };
    const artifact = {
      artifact_key: "material-scope",
      artifact_type: "material_scope",
      branch_key: "project",
      current_submitted_version: {
        id: "01960000-0000-7000-8000-000000000005",
        version_no: 1,
      },
      id: "01960000-0000-7000-8000-000000000004",
      project_id: material.project_id,
      status: "in_review",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          data: { items: [material] },
          meta: { next_cursor: "materials-next" },
          request_id: "request-materials",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ data: artifact, request_id: "request-scope" }, { status: 201 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      listProjectMaterialsPage({
        cursor: "materials-cursor",
        limit: 15,
        projectId: material.project_id,
      }),
    ).resolves.toEqual({ items: [material], nextCursor: "materials-next" });
    await expect(
      createMaterialScopeVersion({
        idempotencyKey: "material-scope-version-1",
        input: {
          material_parse_version_id: "01960000-0000-7000-8000-000000000006",
          page_end: 5,
          page_start: 3,
          source_material_id: material.id,
        },
        projectId: material.project_id,
      }),
    ).resolves.toEqual(artifact);

    const listUrl = new URL((fetchMock.mock.calls[0]?.[0] as Request).url);
    expect(listUrl.searchParams.get("page[cursor]")).toBe("materials-cursor");
    expect(listUrl.searchParams.get("page[limit]")).toBe("15");
    const createRequest = fetchMock.mock.calls[1]?.[0] as Request;
    expect(createRequest.headers.get("Idempotency-Key")).toBe("material-scope-version-1");
    await expect(createRequest.json()).resolves.toEqual({
      material_parse_version_id: "01960000-0000-7000-8000-000000000006",
      page_end: 5,
      page_start: 3,
      source_material_id: material.id,
    });
  });
});
