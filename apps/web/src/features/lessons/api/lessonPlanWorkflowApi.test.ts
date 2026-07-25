import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getLessonPlanArtifact,
  startLessonPlanQualityValidation,
} from "@/features/artifacts/api/artifactsApi";
import { listLessonPlanGenerationJobs } from "@/features/jobs/api/jobsApi";
import { prepareLessonPlanGeneration, startNodeRun } from "@/features/workflow/api/workflowApi";

const client = vi.hoisted(() => ({ GET: vi.fn(), POST: vi.fn() }));

vi.mock("@/shared/api/client", () => ({
  apiClient: client,
  unwrapApiResult: (result: unknown) => result,
  unwrapApiResultWithResponse: (result: unknown) => ({ body: result }),
}));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";

describe("lesson plan active API adapters", () => {
  beforeEach(() => {
    client.GET.mockReset();
    client.POST.mockReset();
  });

  it("uses exact project and lesson paths to recover artifacts and jobs", async () => {
    client.GET.mockResolvedValueOnce({ data: { artifact: null } });
    await getLessonPlanArtifact({ lessonId, projectId });

    expect(client.GET).toHaveBeenNthCalledWith(
      1,
      "/projects/{project_id}/lessons/{lesson_id}/lesson-plan/artifact",
      { params: { path: { lesson_id: lessonId, project_id: projectId } } },
    );

    client.GET.mockResolvedValueOnce({ data: { items: [] } });
    await listLessonPlanGenerationJobs({ lessonId, projectId });

    expect(client.GET).toHaveBeenNthCalledWith(
      2,
      "/projects/{project_id}/lessons/{lesson_id}/lesson-plan/generation-jobs",
      { params: { path: { lesson_id: lessonId, project_id: projectId } } },
    );
  });

  it("uses exact lesson, node run, and artifact version paths for commands", async () => {
    client.POST.mockResolvedValueOnce({ data: { id: "node-run-1" } });
    await prepareLessonPlanGeneration({ idempotencyKey: "prepare-1", lessonId });
    expect(client.POST).toHaveBeenNthCalledWith(1, "/lessons/{lesson_id}/lesson-plan/node-runs", {
      params: {
        header: { "Idempotency-Key": "prepare-1" },
        path: { lesson_id: lessonId },
      },
    });

    client.POST.mockResolvedValueOnce({ data: { job_id: "job-1" } });
    await startNodeRun({
      idempotencyKey: "start-1",
      nodeRunId: "node-run-1",
      userRevision: "突出课堂练习",
    });
    expect(client.POST).toHaveBeenNthCalledWith(2, "/node-runs/{node_run_id}/start", {
      body: { user_revision: "突出课堂练习" },
      params: {
        header: { "Idempotency-Key": "start-1" },
        path: { node_run_id: "node-run-1" },
      },
    });

    client.POST.mockResolvedValueOnce({ data: { node_run_id: "quality-run-1" } });
    await startLessonPlanQualityValidation({
      artifactVersionId: "artifact-version-1",
      idempotencyKey: "quality-1",
      lessonId,
    });
    expect(client.POST).toHaveBeenNthCalledWith(
      3,
      "/lessons/{lesson_id}/lesson-plan/artifact-versions/{artifact_version_id}/quality-validations",
      {
        params: {
          header: { "Idempotency-Key": "quality-1" },
          path: {
            artifact_version_id: "artifact-version-1",
            lesson_id: lessonId,
          },
        },
      },
    );
  });
});
