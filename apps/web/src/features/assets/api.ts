import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useProjectAssets(projectId: string, filters?: { kind?: string; lesson_id?: string }) {
  const normalized: Record<string, string> = {};
  if (filters?.kind && filters.kind !== "all") normalized.kind = filters.kind;
  if (filters?.lesson_id) normalized.lesson_id = filters.lesson_id;
  return useQuery({
    queryKey: qk.projects.assets(projectId, normalized),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/assets", {
          params: { path: { project_id: projectId }, query: normalized },
        }),
      );
      return result.data;
    },
  });
}

export function useDownloadAssetVersion() {
  return useMutation({
    mutationFn: async (assetVersionId: string) => {
      const result = unwrap(
        await client.POST("/asset-versions/{asset_version_id}/download", {
          params: { path: { asset_version_id: assetVersionId } },
        }),
      );
      return result.data;
    },
  });
}

export function useDelivery(projectId: string) {
  return useQuery({
    queryKey: qk.projects.delivery(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/delivery", {
          params: { path: { project_id: projectId } },
        }),
      );
      return result.data;
    },
    refetchInterval: (query) => (query.state.data?.status === "packaging" ? 2_500 : false),
  });
}

export function useCreateDeliveryPackage(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = unwrap(
        await client.POST("/projects/{project_id}/delivery/package", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("delivery") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.delivery(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}
