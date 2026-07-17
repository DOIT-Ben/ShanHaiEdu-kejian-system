import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import { create } from "zustand";
import { createEventStream, qk, type ConnectionMode, type StreamEvent } from "@/shared/api";
import { env } from "@/shared/config/env";

/**
 * 全局 SSE 通道：事件只触发 TanStack Query 失效，绝不直接写状态（06 §5）。
 * 断线退避重连 + Last-Event-ID 续传（sessionStorage 存游标，刷新后继续）。
 * 重连成功后做一次 REST 对账（失效活跃任务查询）。
 */

interface EventChannelState {
  mode: ConnectionMode;
  setMode: (mode: ConnectionMode) => void;
}

export const useEventChannelStore = create<EventChannelState>((set) => ({
  mode: "connecting",
  setMode: (mode) => set({ mode }),
}));

const LAST_EVENT_KEY = "shanhai:last-event-id";

export function invalidateForEvent(queryClient: QueryClient, event: StreamEvent): void {
  const { type, id } = event.resource;
  const projectId = event.project_id;
  const touchWorkflow = () => {
    if (projectId) {
      void queryClient.invalidateQueries({ queryKey: qk.projects.workflow(projectId) });
      void queryClient.invalidateQueries({ queryKey: qk.projects.lessons(projectId) });
    }
  };
  switch (type) {
    case "generation_job": {
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      const nodeRunId = event.payload["node_run_id"];
      if (typeof nodeRunId === "string") {
        void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(nodeRunId) });
        void queryClient.invalidateQueries({ queryKey: ["node-runs", nodeRunId, "results"] });
      }
      const batchId = event.payload["batch_id"];
      if (typeof batchId === "string") {
        void queryClient.invalidateQueries({ queryKey: qk.batches.detail(batchId) });
        void queryClient.invalidateQueries({ queryKey: qk.batches.results(batchId) });
      }
      if (event.event_type === "generation_job.finished") {
        void queryClient.invalidateQueries({ queryKey: qk.home });
        touchWorkflow();
      }
      break;
    }
    case "node_run": {
      void queryClient.invalidateQueries({ queryKey: qk.nodeRuns.detail(id) });
      void queryClient.invalidateQueries({ queryKey: ["node-runs", id] });
      touchWorkflow();
      break;
    }
    case "material": {
      if (projectId) {
        void queryClient.invalidateQueries({ queryKey: qk.projects.material(projectId) });
      }
      touchWorkflow();
      break;
    }
    case "lesson_division": {
      if (projectId) {
        void queryClient.invalidateQueries({ queryKey: qk.projects.division(projectId) });
      }
      touchWorkflow();
      break;
    }
    case "lesson": {
      void queryClient.invalidateQueries({ queryKey: qk.lessons.detail(id) });
      void queryClient.invalidateQueries({ queryKey: qk.lessons.nodeRuns(id) });
      touchWorkflow();
      break;
    }
    case "artifact_version": {
      void queryClient.invalidateQueries({ queryKey: qk.artifacts.version(id) });
      break;
    }
    case "intro_selection": {
      void queryClient.invalidateQueries({ queryKey: ["lessons"] });
      touchWorkflow();
      break;
    }
    case "ppt_page": {
      void queryClient.invalidateQueries({ queryKey: qk.pptPages.detail(id) });
      void queryClient.invalidateQueries({ queryKey: ["lessons"] });
      break;
    }
    case "ppt_style_contract": {
      void queryClient.invalidateQueries({ queryKey: ["lessons"] });
      touchWorkflow();
      break;
    }
    case "video_shot": {
      void queryClient.invalidateQueries({ queryKey: ["video-projects"] });
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      break;
    }
    case "creation_batch": {
      void queryClient.invalidateQueries({ queryKey: qk.batches.detail(id) });
      void queryClient.invalidateQueries({ queryKey: qk.batches.results(id) });
      void queryClient.invalidateQueries({ queryKey: qk.batches.all });
      break;
    }
    case "asset_version": {
      if (projectId) {
        void queryClient.invalidateQueries({ queryKey: ["projects", projectId, "assets"] });
      }
      void queryClient.invalidateQueries({ queryKey: qk.home });
      break;
    }
    case "delivery": {
      if (projectId) {
        void queryClient.invalidateQueries({ queryKey: qk.projects.delivery(projectId) });
      }
      break;
    }
    case "automation": {
      touchWorkflow();
      void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      break;
    }
    default: {
      // 未知资源类型：宽泛失效项目工作流，保证不漏更新
      touchWorkflow();
    }
  }
}

/** 挂载于 GlobalAppShell：登录区域内保持单一全局事件流。 */
export function useGlobalEventStream(enabled: boolean): void {
  const queryClient = useQueryClient();
  const setMode = useEventChannelStore((s) => s.setMode);

  useEffect(() => {
    if (!enabled) return;
    let reconciled = false;
    const handle = createEventStream({
      url: `${env.apiBaseUrl}/events/stream`,
      initialLastEventId: sessionStorage.getItem(LAST_EVENT_KEY),
      onEvent: (event) => {
        sessionStorage.setItem(LAST_EVENT_KEY, event.event_id);
        invalidateForEvent(queryClient, event);
      },
      onModeChange: (mode) => {
        setMode(mode);
        if (mode === "sse") {
          if (reconciled) {
            // 重连成功：REST 对账，恢复一致状态
            void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
            void queryClient.invalidateQueries({ queryKey: qk.home });
          }
          reconciled = true;
        }
      },
    });
    // 轮询兜底：降级模式下周期对账
    const poll = setInterval(() => {
      if (useEventChannelStore.getState().mode === "polling") {
        void queryClient.invalidateQueries({ queryKey: qk.jobs.all });
      }
    }, 15_000);
    return () => {
      clearInterval(poll);
      handle.close();
    };
  }, [enabled, queryClient, setMode]);
}

export const CONNECTION_MODE_LABELS: Record<ConnectionMode, string | null> = {
  connecting: null,
  sse: null,
  reconnecting: "实时连接中断，正在恢复…",
  polling: "实时通道不可用，已切换为定时刷新",
  offline: null,
};
