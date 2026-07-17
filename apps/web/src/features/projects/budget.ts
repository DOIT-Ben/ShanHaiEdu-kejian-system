import { useMutation, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

/** 预算确认 + 恢复自动执行（全自动项目暂停恢复链）。 */
export function useAuthorizeBudgetAndResume(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { maxMinorUnits: number; reason?: string }) => {
      unwrap(
        await client.POST("/projects/{project_id}/budget-authorizations", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("budget") } },
          body: {
            max_minor_units: input.maxMinorUnits,
            ...(input.reason ? { reason: input.reason } : {}),
          },
        }),
      );
      const resumed = unwrap(
        await client.POST("/projects/{project_id}/automation/resume", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("resume") } },
        }),
      );
      return resumed.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      void queryClient.invalidateQueries({ queryKey: qk.home });
    },
  });
}
