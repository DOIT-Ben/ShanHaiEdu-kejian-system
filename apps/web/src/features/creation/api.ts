import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useBatches(studioType?: "image" | "video" | "presentation") {
  return useQuery({
    queryKey: qk.batches.list(studioType),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/creation-batches", {
          params: { query: studioType ? { studio_type: studioType } : {} },
        }),
      );
      return result.data.items;
    },
  });
}

export function useBatch(batchId: string | null) {
  return useQuery({
    queryKey: qk.batches.detail(batchId ?? "none"),
    enabled: Boolean(batchId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/creation-batches/{batch_id}", {
          params: { path: { batch_id: batchId! } },
        }),
      );
      return { batch: result.data, etag: result.etag };
    },
    refetchInterval: (query) => {
      const items = query.state.data?.batch.items;
      return items?.some((item) => item.status === "queued" || item.status === "running") ? 2_500 : false;
    },
  });
}

export function useCreateBatch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      studioType: "image" | "video" | "presentation";
      title: string;
      creationPackageId?: string;
    }) => {
      const result = unwrap(
        await client.POST("/creation-batches", {
          body: {
            studio_type: input.studioType,
            title: input.title,
            ...(input.creationPackageId ? { creation_package_id: input.creationPackageId } : {}),
          },
          params: { header: { "Idempotency-Key": createIdempotencyKey("batch") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.batches.all });
    },
  });
}

export function useUpdateBatchItem(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { itemKey: string; etag: string; patch: Record<string, unknown> }) => {
      const result = unwrap(
        await client.PATCH("/creation-batches/{batch_id}/items/{item_key}", {
          params: { path: { batch_id: batchId, item_key: input.itemKey }, header: { "If-Match": input.etag } },
          body: input.patch,
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.batches.detail(batchId) });
    },
  });
}

export function useGenerateBatch(batchId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { itemIds: string[] }) => {
      const result = unwrap(
        await client.POST("/creation-batches/{batch_id}/generate", {
          params: { path: { batch_id: batchId }, header: { "Idempotency-Key": createIdempotencyKey("batch-gen") } },
          body: { item_ids: input.itemIds },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.batches.detail(batchId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

export function useBatchResults(batchId: string | null, itemKey?: string) {
  return useQuery({
    queryKey: qk.batches.results(batchId ?? "none", itemKey),
    enabled: Boolean(batchId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/creation-batches/{batch_id}/results", {
          params: {
            path: { batch_id: batchId! },
            query: itemKey ? { item_key: itemKey } : {},
          },
        }),
      );
      return result.data.items;
    },
  });
}

export function useCreationPackage(packageId: string | null) {
  return useQuery({
    queryKey: qk.packages.detail(packageId ?? "none"),
    enabled: Boolean(packageId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/creation-packages/{package_id}", {
          params: { path: { package_id: packageId! } },
        }),
      );
      return result.data;
    },
  });
}
