import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult, unwrapApiResultWithResponse } from "@/shared/api/client";

export type ArtifactDto = components["schemas"]["Artifact"];
export type ArtifactDraftDto = components["schemas"]["ArtifactDraft"];
export type ArtifactVersionDto = components["schemas"]["ArtifactVersion"];
export type ApprovalDto = components["schemas"]["Approval"];
export type CreateArtifactRequest = components["schemas"]["CreateArtifactRequest"];
export type SaveArtifactDraftRequest = components["schemas"]["SaveArtifactDraftRequest"];
export type ReviewArtifactVersionRequest = components["schemas"]["ReviewArtifactVersionRequest"];

export async function createArtifact({
  idempotencyKey,
  input,
  projectId,
}: {
  idempotencyKey: string;
  input: CreateArtifactRequest;
  projectId: string;
}): Promise<ArtifactDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/projects/{project_id}/artifacts", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { project_id: projectId },
      },
    }),
  );
  return response.data;
}

export async function getArtifact(
  artifactId: string,
): Promise<{ artifact: ArtifactDto; etag?: string }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.GET("/artifacts/{artifact_id}", {
      params: { path: { artifact_id: artifactId } },
    }),
  );
  return { artifact: response.body.data, etag: response.etag };
}

export async function saveArtifactDraft({
  artifactId,
  draftBranch,
  etag,
  idempotencyKey,
  input,
}: {
  artifactId: string;
  draftBranch: string;
  etag: string;
  idempotencyKey: string;
  input: SaveArtifactDraftRequest;
}): Promise<{ draft: ArtifactDraftDto; etag?: string }> {
  const response = unwrapApiResultWithResponse(
    await apiClient.PUT("/artifacts/{artifact_id}/drafts/{draft_branch}", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey, "If-Match": etag },
        path: { artifact_id: artifactId, draft_branch: draftBranch },
      },
    }),
  );
  return { draft: response.body.data, etag: response.etag };
}

export async function submitArtifactVersion({
  artifactId,
  draftBranch,
  etag,
  idempotencyKey,
}: {
  artifactId: string;
  draftBranch: string;
  etag: string;
  idempotencyKey: string;
}): Promise<ArtifactVersionDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/artifacts/{artifact_id}/versions", {
      body: { draft_branch: draftBranch },
      params: {
        header: { "Idempotency-Key": idempotencyKey, "If-Match": etag },
        path: { artifact_id: artifactId },
      },
    }),
  );
  return response.data;
}

export async function reviewArtifactVersion({
  artifactVersionId,
  idempotencyKey,
  input,
}: {
  artifactVersionId: string;
  idempotencyKey: string;
  input: ReviewArtifactVersionRequest;
}): Promise<ApprovalDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/artifact-versions/{artifact_version_id}/approvals", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { artifact_version_id: artifactVersionId },
      },
    }),
  );
  return response.data;
}
