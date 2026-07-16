import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { createEventStream, qk, type StreamEvent } from "@/shared/api";
import { env } from "@/shared/config/env";
import { useConnectionStore } from "./connectionStore";

/** SSE 事件 → Query 失效映射（事件不直接写缓存）。 */
export function invalidateForEvent(queryClient: QueryClient, event: StreamEvent): void {
  const { project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: taskId } = event;
  switch (event.event_type) {
    case "task.queued":
    case "task.started":
    case "task.progress":
    case "task.completed":
    case "task.failed":
    case "task.cancelled": {
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
      if (taskId) void queryClient.invalidateQueries({ queryKey: qk.tasks.detail(taskId) });
      void queryClient.invalidateQueries({ queryKey: qk.tasks.mine });
      if (event.event_type === "task.completed" || event.event_type === "task.failed") {
        void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
        if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      }
      if (lessonId && nodeKey) {
        void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
      }
      break;
    }
    case "node.status_changed": {
      if (lessonId) {
        void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
        void queryClient.invalidateQueries({ queryKey: qk.lessons.detail(lessonId) });
        if (nodeKey) void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
      }
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.lessons(projectId) });
      break;
    }
    case "artifact.version_created":
    case "artifact.approved":
    case "artifact.stale": {
      if (lessonId && nodeKey) {
        void queryClient.invalidateQueries({ queryKey: qk.lessons.node(lessonId, nodeKey) });
        void queryClient.invalidateQueries({ queryKey: qk.lessons.workspace(lessonId) });
      }
      if (projectId && !lessonId) {
        // 项目级产物（教材证据 / 课时划分）
        void queryClient.invalidateQueries({ queryKey: qk.projects.evidence(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.projects.divisionVersions(projectId) });
        void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      }
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.deliveryRoot(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
      break;
    }
    case "budget.updated": {
      if (projectId) void queryClient.invalidateQueries({ queryKey: qk.projects.detail(projectId) });
      break;
    }
    case "provider.degraded": {
      void queryClient.invalidateQueries({ queryKey: qk.admin.gatewayOverview });
      void queryClient.invalidateQueries({ queryKey: qk.admin.providers });
      break;
    }
    default:
      break;
  }
}

/**
 * 项目事件流：SSE 优先，连续失败自动降级为 30s 轮询；
 * 断线重连基于 Last-Event-ID 续传。
 */
export function useProjectEventStream(projectId: string | null): void {
  const queryClient = useQueryClient();
  const setMode = useConnectionStore((s) => s.setMode);
  const markEvent = useConnectionStore((s) => s.markEvent);

  useEffect(() => {
    if (!projectId) {
      setMode("offline");
      return;
    }
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    const stopPolling = () => {
      if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
      }
    };
    const handle = createEventStream({
      url: `${env.apiBaseUrl}${env.eventStreamPath}?project_id=${encodeURIComponent(projectId)}`,
      onEvent: (event) => {
        markEvent();
        invalidateForEvent(queryClient, event);
      },
      onModeChange: (mode) => {
        setMode(mode);
        if (mode === "polling") {
          // 轮询降级：30 秒刷新任务与工作区
          stopPolling();
          pollTimer = setInterval(() => {
            void queryClient.invalidateQueries({ queryKey: qk.projects.tasksRoot(projectId) });
            void queryClient.invalidateQueries({ queryKey: qk.tasks.mine });
            void queryClient.invalidateQueries({ queryKey: qk.homeOverview });
          }, 30_000);
        } else {
          stopPolling();
        }
      },
    });
    return () => {
      stopPolling();
      handle.close();
      setMode("offline");
    };
  }, [projectId, queryClient, setMode, markEvent]);
}
