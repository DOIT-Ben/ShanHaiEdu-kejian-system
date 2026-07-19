import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type GenerationJobDto = components["schemas"]["GenerationJob"];

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
