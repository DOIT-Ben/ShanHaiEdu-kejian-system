import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type CreationBatchDto = components["schemas"]["CreationBatch"];
export type CreateCreationBatchRequest = components["schemas"]["CreateCreationBatchRequest"];
export type PromptVersionDto = components["schemas"]["PromptVersion"];
export type SavePromptVersionRequest = components["schemas"]["SavePromptVersionRequest"];
export type GenerateCreationItemRequest = components["schemas"]["GenerateCreationItemRequest"];
export type AcceptedJobDto = components["schemas"]["AcceptedJobEnvelope"]["data"];
export type AdoptionDto = components["schemas"]["Adoption"];
export type SaveAdoptionToProjectRequest = components["schemas"]["SaveAdoptionToProjectRequest"];
export type SaveToProjectOperationDto = components["schemas"]["SaveToProjectOperation"];

export async function createCreationBatch({
  idempotencyKey,
  input,
}: {
  idempotencyKey: string;
  input: CreateCreationBatchRequest;
}): Promise<CreationBatchDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/creation-batches", {
      body: input,
      params: { header: { "Idempotency-Key": idempotencyKey } },
    }),
  );
  if (!("source_kind" in response.data)) {
    throw new Error("服务返回了旧版创作批次，请刷新后重试");
  }
  return response.data;
}

export async function saveCreationPromptVersion({
  idempotencyKey,
  input,
  itemId,
}: {
  idempotencyKey: string;
  input: SavePromptVersionRequest;
  itemId: string;
}): Promise<PromptVersionDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/creation-items/{item_id}/prompt-versions", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { item_id: itemId },
      },
    }),
  );
  return response.data;
}

export async function generateCreationItem({
  idempotencyKey,
  input,
  itemId,
}: {
  idempotencyKey: string;
  input: GenerateCreationItemRequest;
  itemId: string;
}): Promise<AcceptedJobDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/creation-items/{item_id}/generate", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { item_id: itemId },
      },
    }),
  );
  return response.data;
}

export async function adoptGenerationResult({
  idempotencyKey,
  reason,
  resultId,
}: {
  idempotencyKey: string;
  reason?: string;
  resultId: string;
}): Promise<AdoptionDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/generation-results/{result_id}/adoptions", {
      body: { reason },
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { result_id: resultId },
      },
    }),
  );
  return response.data;
}

export async function saveAdoptionToProject({
  adoptionId,
  idempotencyKey,
  input,
}: {
  adoptionId: string;
  idempotencyKey: string;
  input: SaveAdoptionToProjectRequest;
}): Promise<SaveToProjectOperationDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/adoptions/{adoption_id}/save-to-project", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { adoption_id: adoptionId },
      },
    }),
  );
  return response.data;
}
