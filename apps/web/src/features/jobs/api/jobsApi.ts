import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type GenerationJobDto = components["schemas"]["GenerationJob"];

export async function listProjectGenerationJobsPage({
  cursor,
  lessonId,
  limit,
  projectId,
}: {
  cursor?: string;
  lessonId?: string;
  limit?: number;
  projectId: string;
}): Promise<{ items: GenerationJobDto[]; nextCursor: string | null }> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/generation-jobs", {
      params: {
        path: { project_id: projectId },
        query: {
          lesson_id: lessonId,
          "page[cursor]": cursor,
          "page[limit]": limit,
        },
      },
    }),
  );
  return { items: response.data.items, nextCursor: response.meta.next_cursor };
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
