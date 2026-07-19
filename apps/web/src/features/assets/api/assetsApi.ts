import type { components } from "@/generated/api-schema";
import { apiClient, unwrapApiResult } from "@/shared/api/client";

export type ProjectAssetSlotDto = components["schemas"]["ProjectAssetSlot"];
export type AssetBindingDto = components["schemas"]["AssetBinding"];
export type BindAssetRequest = components["schemas"]["BindAssetRequest"];

export async function listProjectAssetSlots({
  cursor,
  lessonUnitId,
  limit = 100,
  projectId,
  slotKey,
}: {
  cursor?: string;
  lessonUnitId?: string;
  limit?: number;
  projectId: string;
  slotKey?: string;
}): Promise<{ items: ProjectAssetSlotDto[]; nextCursor?: string }> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/asset-slots", {
      params: {
        path: { project_id: projectId },
        query: {
          lesson_unit_id: lessonUnitId,
          "page[cursor]": cursor,
          "page[limit]": limit,
          slot_key: slotKey,
        },
      },
    }),
  );
  return {
    items: response.data.items,
    nextCursor: response.meta.next_cursor ?? undefined,
  };
}

export async function getProjectAssetPackage({
  cursor,
  lessonUnitId,
  limit = 100,
  projectId,
  slotKey,
}: {
  cursor?: string;
  lessonUnitId?: string;
  limit?: number;
  projectId: string;
  slotKey?: string;
}): Promise<{ items: ProjectAssetSlotDto[]; nextCursor?: string; projectId: string }> {
  const response = unwrapApiResult(
    await apiClient.GET("/projects/{project_id}/asset-package", {
      params: {
        path: { project_id: projectId },
        query: {
          lesson_unit_id: lessonUnitId,
          "page[cursor]": cursor,
          "page[limit]": limit,
          slot_key: slotKey,
        },
      },
    }),
  );
  return {
    items: response.data.items,
    nextCursor: response.meta.next_cursor ?? undefined,
    projectId: response.data.project_id,
  };
}

export async function bindProjectAsset({
  idempotencyKey,
  input,
  slotId,
}: {
  idempotencyKey: string;
  input: BindAssetRequest;
  slotId: string;
}): Promise<AssetBindingDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/asset-slots/{slot_id}/bindings", {
      body: input,
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { slot_id: slotId },
      },
    }),
  );
  return response.data;
}

export async function unbindProjectAsset({
  bindingId,
  idempotencyKey,
}: {
  bindingId: string;
  idempotencyKey: string;
}): Promise<AssetBindingDto> {
  const response = unwrapApiResult(
    await apiClient.POST("/asset-bindings/{binding_id}/unbind", {
      params: {
        header: { "Idempotency-Key": idempotencyKey },
        path: { binding_id: bindingId },
      },
    }),
  );
  return response.data;
}
