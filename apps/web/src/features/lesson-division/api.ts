import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export interface DivisionEntryDraft {
  entry_id: string | null;
  title: string;
  focus: string;
  duration_minutes: number;
}

export function useDivision(projectId: string) {
  return useQuery({
    queryKey: qk.projects.division(projectId),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/projects/{project_id}/lesson-division", {
          params: { path: { project_id: projectId } },
        }),
      );
      return { division: result.data, etag: result.etag };
    },
    refetchInterval: (query) => {
      const status = query.state.data?.division.status;
      return status === "not_ready" ? 2_500 : false;
    },
  });
}

export function useSaveDivision(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { etag: string; entries: DivisionEntryDraft[] }) => {
      const result = unwrap(
        await client.PUT("/projects/{project_id}/lesson-division", {
          params: { path: { project_id: projectId }, header: { "If-Match": input.etag } },
          body: { entries: input.entries },
        }),
      );
      return { division: result.data, etag: result.etag };
    },
    onSuccess: (data) => {
      queryClient.setQueryData(qk.projects.division(projectId), data);
    },
  });
}

export function useApproveDivision(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = unwrap(
        await client.POST("/projects/{project_id}/lesson-division/approve", {
          params: { path: { project_id: projectId }, header: { "Idempotency-Key": createIdempotencyKey("division-approve") } },
        }),
      );
      return result.data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.lessons(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(projectId) });
    },
  });
}
