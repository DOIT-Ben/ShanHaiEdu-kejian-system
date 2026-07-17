import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export type ReplaceMode = "reject_if_occupied" | "replace_active" | "append";

/** 保存到项目：唯一入库通道（03 §4 主操作状态链的最后一环）。 */
export function useSaveToProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      resultId: string;
      projectId: string;
      slotKey: string;
      replaceMode: ReplaceMode;
    }) => {
      const result = unwrap(
        await client.POST("/generation-results/{result_id}/save-to-project", {
          params: { path: { result_id: input.resultId }, header: { "Idempotency-Key": createIdempotencyKey("save") } },
          body: {
            project_id: input.projectId,
            slot_key: input.slotKey,
            replace_mode: input.replaceMode,
          },
        }),
      );
      return result.data;
    },
    onSuccess: (_data, input) => {
      void queryClient.invalidateQueries({ queryKey: ["projects", input.projectId, "assets"] });
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(input.projectId) });
      void queryClient.invalidateQueries({ queryKey: ["lessons"] });
      void queryClient.invalidateQueries({ queryKey: ["video-projects"] });
      void queryClient.invalidateQueries({ queryKey: ["node-runs"] });
      void queryClient.invalidateQueries({ queryKey: qk.batches.all });
      void queryClient.invalidateQueries({ queryKey: qk.home });
    },
  });
}

export function useDownloadResult() {
  return useMutation({
    mutationFn: async (resultId: string) => {
      const result = unwrap(
        await client.POST("/generation-results/{result_id}/download", {
          params: { path: { result_id: resultId } },
        }),
      );
      return result.data;
    },
  });
}
