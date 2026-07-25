import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type GenerationJobDto = components["schemas"]["GenerationJob"];

export async function listLessonPlanGenerationJobs({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}): Promise<GenerationJobDto[]> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/lessons/{lesson_id}/lesson-plan/generation-jobs", {
      params: { path: { lesson_id: lessonId, project_id: projectId } },
    }),
  );
  return response.data.items;
}

export async function listLessonDivisionGenerationJobs(
  projectId: string,
): Promise<GenerationJobDto[]> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/lesson-division/generation-jobs", {
      params: { path: { project_id: projectId } },
    }),
  );
  return response.data.items;
}

export async function getGenerationJob(jobId: string): Promise<GenerationJobDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/generation-jobs/{job_id}", {
      params: { path: { job_id: jobId } },
    }),
  );
  return response.data;
}

export async function cancelGenerationJob({
  idempotencyKey,
  jobId,
}: {
  idempotencyKey: string;
  jobId: string;
}): Promise<GenerationJobDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/generation-jobs/{job_id}/cancel", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { job_id: jobId },
      },
    }),
  );
  return response.data;
}
