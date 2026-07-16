import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useDelivery(projectId: string, lessonId?: string) {
  return useQuery({
    queryKey: qk.projects.delivery(projectId, lessonId),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/delivery", {
        params: { path: { projectId }, query: { lesson_id: lessonId } },
      });
      return unwrap(result).data;
    },
  });
}

export function useStartPackage(projectId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const result = await client.POST("/projects/{projectId}/delivery/package-runs", {
        params: {
          path: { projectId },
          header: { "Idempotency-Key": createIdempotencyKey("pkg") },
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.projects.deliveryRoot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
    },
  });
}
