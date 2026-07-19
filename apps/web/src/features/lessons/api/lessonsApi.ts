import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResultWithResponse } from "@/shared/api/client";

export type LessonDto = components["schemas"]["Lesson"];
export type UpdateLessonCollectionRequest = components["schemas"]["UpdateLessonCollectionRequest"];
export type UpdateLessonBranchesRequest = components["schemas"]["UpdateLessonBranchesRequest"];

export async function listProjectLessons(
  projectId: string,
): Promise<{ etag?: string; lessons: LessonDto[]; lockVersion: number }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/projects/{project_id}/lessons", {
      params: { path: { project_id: projectId } },
    }),
  );
  return {
    etag: response.etag,
    lessons: response.body.data.items,
    lockVersion: response.body.data.lock_version,
  };
}

export async function updateProjectLessons({
  etag,
  idempotencyKey,
  input,
  projectId,
}: {
  etag: string;
  idempotencyKey: string;
  input: UpdateLessonCollectionRequest;
  projectId: string;
}): Promise<{ etag?: string; lessons: LessonDto[]; lockVersion: number }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.PATCH("/projects/{project_id}/lessons", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey, "If-Match": etag },
        path: { project_id: projectId },
      },
    }),
  );
  return {
    etag: response.etag,
    lessons: response.body.data.items,
    lockVersion: response.body.data.lock_version,
  };
}

export async function getLesson(lessonId: string): Promise<{ etag?: string; lesson: LessonDto }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/lessons/{lesson_id}", {
      params: { path: { lesson_id: lessonId } },
    }),
  );
  return { etag: response.etag, lesson: response.body.data };
}

export async function updateLessonBranches({
  etag,
  idempotencyKey,
  input,
  lessonId,
}: {
  etag: string;
  idempotencyKey: string;
  input: UpdateLessonBranchesRequest;
  lessonId: string;
}): Promise<{ etag?: string; lesson: LessonDto }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.PATCH("/lessons/{lesson_id}/branches", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey, "If-Match": etag },
        path: { lesson_id: lessonId },
      },
    }),
  );
  return { etag: response.etag, lesson: response.body.data };
}
