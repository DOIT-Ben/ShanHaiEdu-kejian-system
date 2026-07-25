import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getIntroOptionArtifact,
  listIntroOptionGenerationJobs,
  prepareIntroOptionGeneration,
  selectLessonIntroOption,
  startIntroOptionQualityValidation,
} from "@/features/intro-options/api/introOptionsApi";

const client = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));

vi.mock("@/shared/api/client", () => ({
  apiClient: client,
  unwrapApiResult: (result: unknown) => result,
}));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";

describe("intro options active API adapters", () => {
  beforeEach(() => {
    client.GET.mockReset();
    client.POST.mockReset();
  });

  it("uses exact project and lesson paths to recover artifacts and jobs", async () => {
    client.GET.mockResolvedValueOnce({ data: { artifact: null } });
    await getIntroOptionArtifact({ lessonId, projectId });
    expect(client.GET).toHaveBeenNthCalledWith(
      1,
      "/projects/{project_id}/lessons/{lesson_id}/intro-options/artifact",
      { params: { path: { lesson_id: lessonId, project_id: projectId } } },
    );

    client.GET.mockResolvedValueOnce({ data: { items: [] } });
    await listIntroOptionGenerationJobs({ lessonId, projectId });
    expect(client.GET).toHaveBeenNthCalledWith(
      2,
      "/projects/{project_id}/lessons/{lesson_id}/intro-options/generation-jobs",
      { params: { path: { lesson_id: lessonId, project_id: projectId } } },
    );
  });

  it("binds generation, quality, and selection commands to exact lesson facts", async () => {
    client.POST.mockResolvedValueOnce({ data: { id: "node-run-1" } });
    await prepareIntroOptionGeneration({ idempotencyKey: "prepare-intro", lessonId });
    expect(client.POST).toHaveBeenNthCalledWith(1, "/lessons/{lesson_id}/intro-options/node-runs", {
      body: { generation_mode: "default_nine", source_artifact_version_id: null },
      params: {
        header: { "Idempotency-Key": "prepare-intro" },
        path: { lesson_id: lessonId },
      },
    });

    client.POST.mockResolvedValueOnce({ data: { node_run_id: "quality-run-1" } });
    await startIntroOptionQualityValidation({
      artifactVersionId: "version-1",
      idempotencyKey: "quality-intro",
      lessonId,
    });
    expect(client.POST).toHaveBeenNthCalledWith(
      2,
      "/lessons/{lesson_id}/intro-options/artifact-versions/{artifact_version_id}/quality-validations",
      {
        params: {
          header: { "Idempotency-Key": "quality-intro" },
          path: { artifact_version_id: "version-1", lesson_id: lessonId },
        },
      },
    );

    client.POST.mockResolvedValueOnce({ data: { option_key: "INTRO-SCI-01" } });
    await selectLessonIntroOption({
      artifactVersionId: "version-1",
      idempotencyKey: "select-intro",
      lessonId,
      optionKey: "INTRO-SCI-01",
    });
    expect(client.POST).toHaveBeenNthCalledWith(3, "/lessons/{lesson_id}/intro-selections", {
      body: { artifact_version_id: "version-1", option_key: "INTRO-SCI-01" },
      params: {
        header: { "Idempotency-Key": "select-intro" },
        path: { lesson_id: lessonId },
      },
    });
  });
});
