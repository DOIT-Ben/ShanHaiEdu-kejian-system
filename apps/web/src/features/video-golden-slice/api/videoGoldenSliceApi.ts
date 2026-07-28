import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type VideoGoldenSliceDto = components["schemas"]["VideoGoldenSlice"];
export type AcceptedVideoJobDto = components["schemas"]["AcceptedJobEnvelope"]["data"];
export type VideoAdoptionDto = components["schemas"]["Adoption"];
export type SaveVideoOperationDto = components["schemas"]["SaveToProjectOperation"];

export async function getVideoGoldenSlice({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}): Promise<VideoGoldenSliceDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/lessons/{lesson_id}/video", {
      params: { path: { lesson_id: lessonId, project_id: projectId } },
    }),
  );
  return response.data;
}

export async function startVideoGeneration({
  idempotencyKey,
  keyframeFileAssetVersionId,
  lessonId,
  projectId,
}: {
  idempotencyKey: string;
  keyframeFileAssetVersionId: string;
  lessonId: string;
  projectId: string;
}): Promise<AcceptedVideoJobDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/projects/{project_id}/lessons/{lesson_id}/video/generations", {
      body: { keyframe_file_asset_version_id: keyframeFileAssetVersionId },
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { lesson_id: lessonId, project_id: projectId },
      },
    }),
  );
  return response.data;
}

export async function adoptVideoResult({
  idempotencyKey,
  lessonId,
  projectId,
  resultId,
}: {
  idempotencyKey: string;
  lessonId: string;
  projectId: string;
  resultId: string;
}): Promise<VideoAdoptionDto> {
  const response = unwrapApiResult(
    await apiClient.POST(
      "/projects/{project_id}/lessons/{lesson_id}/video/results/{result_id}/adoptions",
      {
        body: { reason: "采用这段课堂导入短片" },
        params: {
          header: { "Idempotency-Key": idempotencyKey },
          path: { lesson_id: lessonId, project_id: projectId, result_id: resultId },
        },
      },
    ),
  );
  return response.data;
}

export async function saveVideoAdoption({
  adoptionId,
  idempotencyKey,
  lessonId,
  projectId,
}: {
  adoptionId: string;
  idempotencyKey: string;
  lessonId: string;
  projectId: string;
}): Promise<SaveVideoOperationDto> {
  const response = unwrapApiResult(
    await apiClient.POST(
      "/projects/{project_id}/lessons/{lesson_id}/video/adoptions/{adoption_id}/save",
      {
        body: { replace_mode: "replace_active" },
        params: {
          header: { "Idempotency-Key": idempotencyKey },
          path: { adoption_id: adoptionId, lesson_id: lessonId, project_id: projectId },
        },
      },
    ),
  );
  return response.data;
}
