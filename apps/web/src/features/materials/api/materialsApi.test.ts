import { afterEach, describe, expect, it, vi } from "vitest";
import {
  confirmMaterialUpload,
  createMaterialUploadSession,
  sha256File,
  uploadMaterialFile,
} from "./materialsApi";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  return new Response(JSON.stringify(body), { ...init, headers });
}

describe("materialsApi", () => {
  afterEach(() => vi.unstubAllGlobals());

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
});
