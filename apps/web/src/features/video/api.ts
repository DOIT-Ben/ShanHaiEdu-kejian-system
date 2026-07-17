import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useVideoProject(lessonId: string) {
  return useQuery({
    queryKey: qk.lessons.videoProject(lessonId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/lessons/{lesson_id}/video-project", {
          params: { path: { lesson_id: lessonId } },
        }),
      );
      return result.data ?? null;
    },
  });
}

export function useVideoShots(videoProjectId: string | null) {
  return useQuery({
    queryKey: qk.videoProjects.shots(videoProjectId ?? "none"),
    enabled: Boolean(videoProjectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/video-projects/{video_project_id}/shots", {
          params: { path: { video_project_id: videoProjectId! } },
        }),
      );
      return result.data.items;
    },
    refetchInterval: (query) => {
      const items = query.state.data;
      return items?.some((shot) => shot.status === "generating") ? 2_500 : false;
    },
  });
}

export function useSaveShot(shotId: string, videoProjectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { etag: string; shot: Record<string, unknown> }) => {
      const result = unwrap(
        await client.PUT("/video-shots/{shot_id}", {
          params: { path: { shot_id: shotId }, header: { "If-Match": input.etag } },
          body: { shot: input.shot as never },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.videoProjects.shots(videoProjectId) });
    },
  });
}

export function useGenerateShot(videoProjectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (shotId: string) => {
      const result = unwrap(
        await client.POST("/video-shots/{shot_id}/generate", {
          params: { path: { shot_id: shotId }, header: { "Idempotency-Key": createIdempotencyKey("shot-gen") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.videoProjects.shots(videoProjectId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
    },
  });
}

/** 镜头候选：镜头生成结果挂在 video_clips 节点上，以 shot_key 为 item_key。 */
export function useShotResults(nodeRunId: string | null, shotKey: string | null) {
  return useQuery({
    queryKey: qk.nodeRuns.results(nodeRunId ?? "none", shotKey ?? "none"),
    enabled: Boolean(nodeRunId && shotKey),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/node-runs/{node_run_id}/results", {
          params: {
            path: { node_run_id: nodeRunId! },
            query: { item_key: shotKey! },
          },
        }),
      );
      return result.data.items;
    },
  });
}
