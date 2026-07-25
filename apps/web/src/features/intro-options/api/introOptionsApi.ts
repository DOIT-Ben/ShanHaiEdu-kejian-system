import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type IntroOptionsDto = components["schemas"]["IntroOptions"];
export type IntroOptionDto = components["schemas"]["IntroOption"];
export type IntroOptionVersionDto = components["schemas"]["IntroOptionVersion"];
export type IntroSelectionDto = components["schemas"]["IntroSelection"];

export async function getLessonIntroOptions(lessonId: string): Promise<IntroOptionsDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/lessons/{lesson_id}/intro-options", {
      params: { path: { lesson_id: lessonId } },
    }),
  );
  return response.data;
}

export async function selectLessonIntroOption({
  artifactVersionId,
  idempotencyKey,
  lessonId,
  optionKey,
}: {
  artifactVersionId: string;
  idempotencyKey: string;
  lessonId: string;
  optionKey: string;
}): Promise<IntroSelectionDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/lessons/{lesson_id}/intro-selections", {
      body: { artifact_version_id: artifactVersionId, option_key: optionKey },
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { lesson_id: lessonId },
      },
    }),
  );
  return response.data;
}
