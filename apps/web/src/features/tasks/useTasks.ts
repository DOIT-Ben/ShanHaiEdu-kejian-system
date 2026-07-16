import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { client, qk, unwrap } from "@/shared/api";
import { isTaskActive, type TaskStatus } from "@/shared/lib/status";
import { createIdempotencyKey } from "@/shared/lib/idempotency";

export function useMyTasks(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: qk.tasks.mine,
    queryFn: async () => {
      const result = await client.GET("/tasks", {});
      return unwrap(result).data;
    },
    enabled: options?.enabled ?? true,
  });
}

export interface TaskFilters {
  status?: string;
  lesson_id?: string;
  node_key?: string;
}

export function useProjectTasks(projectId: string, filters: TaskFilters = {}, options?: { refetchInterval?: number | false }) {
  return useQuery({
    queryKey: qk.projects.tasks(projectId, filters as Record<string, unknown>),
    queryFn: async () => {
      const result = await client.GET("/projects/{projectId}/tasks", {
        params: { path: { projectId }, query: { ...filters, page_size: 50 } },
      });
      return unwrap(result).data;
    },
    refetchInterval: options?.refetchInterval ?? false,
  });
}

/** 单任务查询：进行中的任务轮询兜底（SSE 之外的保险）。 */
export function useTask(taskId: string | null) {
  return useQuery({
    queryKey: qk.tasks.detail(taskId ?? "none"),
    queryFn: async () => {
      const result = await client.GET("/tasks/{taskId}", { params: { path: { taskId: taskId! } } });
      return unwrap(result).data;
    },
    enabled: Boolean(taskId),
    refetchInterval: (query) => {
      const task = query.state.data;
      return task && isTaskActive(task.status as TaskStatus) ? 2000 : false;
    },
  });
}

export function useCancelTask(projectId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      const result = await client.POST("/tasks/{taskId}/cancel", { params: { path: { taskId } } });
      return unwrap(result).data;
    },
    onSuccess: (task) => {
      queryClient.setQueryData(qk.tasks.detail(task.task_id), task);
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.tasks.mine });
    },
  });
}

export function useRetryTask(projectId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (taskId: string) => {
      const result = await client.POST("/tasks/{taskId}/retry", {
        params: {
          path: { taskId },
          header: { "Idempotency-Key": createIdempotencyKey("retry") },
        },
      });
      return unwrap(result).data;
    },
    onSuccess: () => {
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.tasks.mine });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
    },
  });
}
