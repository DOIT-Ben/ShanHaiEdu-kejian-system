import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as materialsApi from "@/features/materials/api/materialsApi";
import { ProjectMaterialUploadPanel } from "@/features/materials/components/ProjectMaterialUploadPanel";

vi.mock("@/shared/api/client", () => ({ isCsrfTokenAvailable: () => true }));

describe("ProjectMaterialUploadPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("uploads and confirms a PDF against the existing exact project", async () => {
    vi.spyOn(materialsApi, "sha256File").mockResolvedValue("a".repeat(64));
    vi.spyOn(materialsApi, "createMaterialUploadSession").mockResolvedValue({
      expires_at: "2026-07-25T00:00:00Z",
      material_id: "material-1",
      method: "PUT",
      required_headers: {},
      upload_session_id: "upload-1",
      upload_url: "https://storage.example.test/upload-1",
    });
    vi.spyOn(materialsApi, "uploadMaterialFile").mockResolvedValue("etag-1");
    vi.spyOn(materialsApi, "confirmMaterialUpload").mockResolvedValue({
      events_url: "/generation-jobs/job-1/events/stream",
      job_id: "job-1",
      status: "queued",
    });
    const accepted = vi.fn();
    render(<ProjectMaterialUploadPanel onAccepted={accepted} projectId="project-1" />);
    const file = new File(["controlled pdf"], "teacher-textbook.pdf", {
      lastModified: 1,
      type: "application/pdf",
    });

    fireEvent.change(screen.getByLabelText("选择教材 PDF"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "上传并解析教材" }));

    await waitFor(() =>
      expect(accepted).toHaveBeenCalledWith({ jobId: "job-1", materialId: "material-1" }),
    );
    const uploadSessionInput = vi.mocked(materialsApi.createMaterialUploadSession).mock
      .calls[0]?.[0];
    expect(uploadSessionInput?.input.filename).toBe("teacher-textbook.pdf");
    expect(uploadSessionInput?.projectId).toBe("project-1");
    expect(materialsApi.confirmMaterialUpload).toHaveBeenCalledWith(
      expect.objectContaining({ materialId: "material-1", projectId: "project-1" }),
    );
  });
});
