import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { client, downloadFileObject, qk, unwrap } from "@/shared/api";
import { toast } from "@/shared/ui";

export interface AssetFilters {
  type?: string;
  status?: string;
  source_node_key?: string;
  lesson_id?: string;
  keyword?: string;
}

export function useProjectAssets(projectId: string, filters: AssetFilters = {}) {
  return useInfiniteQuery({
    queryKey: qk.projects.assets(projectId, filters as Record<string, unknown>),
    queryFn: async ({ pageParam }) => {
      const result = await client.GET("/projects/{projectId}/assets", {
        params: {
          path: { projectId },
          query: {
            type: filters.type,
            status: filters.status,
            source_node_key: filters.source_node_key,
            lesson_id: filters.lesson_id,
            keyword: filters.keyword || undefined,
            cursor: pageParam || undefined,
            page_size: 40,
          },
        },
      });
      const { data, meta } = unwrap(result);
      return { assets: data, nextCursor: meta.next_cursor ?? null };
    },
    initialPageParam: "",
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });
}

export function useAssetDetail(assetId: string | null) {
  return useQuery({
    queryKey: qk.assets.detail(assetId ?? "none"),
    queryFn: async () => {
      const result = await client.GET("/assets/{assetId}", { params: { path: { assetId: assetId! } } });
      return unwrap(result).data;
    },
    enabled: Boolean(assetId),
  });
}

/** 短时授权下载：授权失败给出可见错误，不静默。 */
export function useDownloadFile() {
  return useMutation({
    mutationFn: async (input: { fileObjectId: string; fileName?: string }) => {
      await downloadFileObject(input.fileObjectId, input.fileName);
    },
    onError: () => {
      toast({ tone: "danger", title: "下载失败", description: "获取下载授权失败，请稍后重试。" });
    },
  });
}
