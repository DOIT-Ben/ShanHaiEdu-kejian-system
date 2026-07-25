import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type IntroOptionsDto = components["schemas"]["IntroOptions"];
export type IntroOptionArtifactDto = components["schemas"]["IntroOptionArtifactEnvelope"]["data"];
export type IntroOptionDto = components["schemas"]["option"];
export type IntroOptionSetDto = components["schemas"]["intro-option-set.schema"];
export type IntroOptionSetPublicDto = components["schemas"]["IntroOptionSetPublic"];
export type IntroSelectionDto = components["schemas"]["IntroSelection"];
export type GenerationJobDto = components["schemas"]["GenerationJob"];
export type AcceptedNodeRunDto = components["schemas"]["AcceptedNodeRunEnvelope"]["data"];
export type NodeRunDto = components["schemas"]["NodeRun"];

export async function getIntroOptionArtifact({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}): Promise<IntroOptionArtifactDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/lessons/{lesson_id}/intro-options/artifact", {
      params: { path: { lesson_id: lessonId, project_id: projectId } },
    }),
  );
  return response.data;
}

export async function getLessonIntroOptions(lessonId: string): Promise<IntroOptionsDto> {
  const response = unwrapApiResult(
    await apiClient.GET("/lessons/{lesson_id}/intro-options", {
      params: { path: { lesson_id: lessonId } },
    }),
  );
  return response.data;
}

export async function listIntroOptionGenerationJobs({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}): Promise<GenerationJobDto[]> {
  const response = unwrapApiResult(
    await apiClient.GET(
      "/projects/{project_id}/lessons/{lesson_id}/intro-options/generation-jobs",
      { params: { path: { lesson_id: lessonId, project_id: projectId } } },
    ),
  );
  return response.data.items;
}

export async function prepareIntroOptionGeneration({
  idempotencyKey,
  lessonId,
}: {
  idempotencyKey: string;
  lessonId: string;
}): Promise<NodeRunDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/lessons/{lesson_id}/intro-options/node-runs", {
      body: { generation_mode: "default_nine", source_artifact_version_id: null },
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { lesson_id: lessonId },
      },
    }),
  );
  return response.data;
}

export async function startIntroOptionQualityValidation({
  artifactVersionId,
  idempotencyKey,
  lessonId,
}: {
  artifactVersionId: string;
  idempotencyKey: string;
  lessonId: string;
}): Promise<AcceptedNodeRunDto> {
  const response = unwrapApiResult(
    await apiClient.POST(
      "/lessons/{lesson_id}/intro-options/artifact-versions/{artifact_version_id}/quality-validations",
      {
        params: {
          header: { "Idempotency-Key": idempotencyKey },
          path: { artifact_version_id: artifactVersionId, lesson_id: lessonId },
        },
      },
    ),
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
