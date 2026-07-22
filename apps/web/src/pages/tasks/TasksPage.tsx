import {
  CheckCircle2,
  CloudOff,
  LoaderCircle,
  PauseCircle,
  RefreshCw,
  RotateCcw,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { saveMockDraft, updateMockTask, useMockRuntime } from "@/shared/api/mockClient";
import { apiConfig } from "@/shared/api/config";
import { demoProjectId } from "@/shared/data/mockData";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import type { MockRuntimeState, MockTask } from "@/shared/api/mockClient";

const actionStatuses = new Set([
  "queued",
  "review_required",
  "failed",
  "partially_completed",
  "stale",
]);

function taskTime(updatedAt: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(updatedAt));
}

function taskTarget(runtime: MockRuntimeState, task: MockTask, projectId: string) {
  const node = Object.values(runtime.nodeStates).find((item) => item.id === task.node_run_id);
  if (
    node?.lesson_id &&
    node.project_id === projectId &&
    getApprovedProjectLessons(runtime, projectId).some((lesson) => lesson.id === node.lesson_id)
  ) {
    return `/app/projects/${projectId}/lessons/${node.lesson_id}/work/${node.node_key}`;
  }
  const firstLessonId = getApprovedProjectLessons(runtime, projectId)[0]?.id;
  return firstLessonId
    ? `/app/projects/${projectId}/lessons/${firstLessonId}/work/lesson-plan`
    : `/app/projects/${projectId}/materials`;
}

export function TasksPage({ projectOnly = false }: { projectOnly?: boolean }) {
  const { projectId: routeProjectId } = useParams();
  const [searchParams] = useSearchParams();
  const runtime = useMockRuntime();
  const [filter, setFilter] = useState("all");
  const [connectionRequest, setConnectionRequest] = useState<"idle" | "pending" | "error">("idle");
  const reconnectTimer = useRef<number | null>(null);
  const connectionKey = projectOnly
    ? `project:${routeProjectId ?? ""}:events-connected`
    : "tasks:events-connected";
  const connectionValue = runtime.drafts[connectionKey]?.value;
  const connected =
    connectionValue === true ||
    (typeof connectionValue === "object" &&
      connectionValue !== null &&
      "status" in connectionValue &&
      connectionValue.status === "connected");
  const isMockMode = apiConfig.mode === "mock";
  const projectTasks = projectOnly
    ? runtime.tasks.filter((task) => task.project_id === routeProjectId)
    : runtime.tasks;
  const tasks = projectTasks.filter((task) => {
    if (filter === "all") return true;
    if (filter === "running") return task.status === "running" || task.status === "paused";
    return actionStatuses.has(task.status);
  });
  useEffect(
    () => () => {
      if (reconnectTimer.current !== null) window.clearTimeout(reconnectTimer.current);
    },
    [],
  );
  const reconnect = () => {
    if (reconnectTimer.current !== null) window.clearTimeout(reconnectTimer.current);
    setConnectionRequest("pending");
    reconnectTimer.current = window.setTimeout(() => {
      reconnectTimer.current = null;
      if (searchParams.get("scenario") === "connection_error") {
        setConnectionRequest("error");
        return;
      }
      saveMockDraft(
        connectionKey,
        { checkedAt: new Date().toISOString(), status: "connected" },
        { projectId: projectOnly ? routeProjectId : undefined },
      );
      setConnectionRequest("idle");
    }, 450);
  };

  return (
    <div className="mx-auto max-w-[1200px] px-4 py-4 md:px-6">
      <FocusPageHeader
        description={
          projectOnly
            ? "查看本项目正在运行、等待确认和需要处理的任务。"
            : isMockMode
              ? "这里汇总正在准备、等待确认和需要重新处理的课堂作品。"
              : "离开制作页面不会中断任务；返回后会继续显示最新状态。"
        }
        supporting={
          <div className="flex min-w-0 flex-wrap items-center gap-2 md:justify-end">
            <div
              aria-label="任务筛选"
              className="inline-flex rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-1"
              role="group"
            >
              {[
                { label: "全部", value: "all" },
                { label: "进行中", value: "running" },
                { label: "等待处理", value: "action" },
              ].map((item) => (
                <button
                  aria-pressed={filter === item.value}
                  className="rounded-md px-3 py-1.5 text-sm data-[state=active]:bg-[var(--sh-surface-elevated)] data-[state=active]:font-semibold data-[state=active]:shadow-sm"
                  data-state={filter === item.value ? "active" : "inactive"}
                  key={item.value}
                  onClick={() => setFilter(item.value)}
                  type="button"
                >
                  {item.label}
                </button>
              ))}
            </div>
            {connected || !isMockMode ? (
              <span className="inline-flex min-h-8 shrink-0 items-center gap-1.5 rounded-full bg-[var(--sh-success-soft)] px-2.5 text-xs font-semibold text-[var(--sh-success)]">
                <CheckCircle2 aria-hidden="true" className="size-3.5" />
                进度实时更新中
              </span>
            ) : null}
          </div>
        }
        title={projectOnly ? "项目任务" : "任务中心"}
      />
      {isMockMode && !connected ? (
        <div
          className="mt-4 flex flex-wrap items-center gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] p-3"
          role={connectionRequest === "error" ? "alert" : undefined}
        >
          <CloudOff aria-hidden="true" className="size-5 text-[var(--sh-warning)]" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
              {connectionRequest === "error" ? "进度仍未恢复" : "进度更新暂时中断"}
            </p>
            <p className="mt-1 text-xs text-[var(--sh-ink-muted)]">
              {connectionRequest === "error"
                ? "请检查网络后重试，正在制作的课堂作品不会受到影响。"
                : "下方任务可以正常查看；恢复后会继续显示最新进度。"}
            </p>
          </div>
          <Button
            disabled={connectionRequest === "pending"}
            onClick={reconnect}
            size="sm"
            variant="secondary"
          >
            {connectionRequest === "pending" ? (
              <LoaderCircle
                aria-hidden="true"
                className="animate-spin motion-reduce:animate-none"
              />
            ) : (
              <RefreshCw aria-hidden="true" />
            )}
            {connectionRequest === "pending"
              ? "正在恢复"
              : connectionRequest === "error"
                ? "重试"
                : "恢复更新"}
          </Button>
        </div>
      ) : null}
      <div className="mt-4 space-y-2">
        {tasks.map((task) => {
          const taskProjectId = task.project_id ?? demoProjectId;
          const confirmationTarget = taskTarget(runtime, task, taskProjectId);
          return (
            <article
              className="rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3 md:grid md:grid-cols-[120px_minmax(0,1fr)_auto] md:items-center md:gap-4"
              data-density="compact"
              key={task.id}
            >
              <div className="flex items-center justify-between gap-3 md:block">
                <StatusBadge status={task.status} />
                <span className="text-xs text-[var(--sh-ink-faint)] md:mt-1 md:block">
                  {taskTime(task.updated_at)}
                </span>
              </div>
              <div className="mt-2 min-w-0 md:mt-0">
                <h2 className="font-semibold text-[var(--sh-ink-strong)]">{task.title}</h2>
                <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">{task.detail}</p>
                {task.status === "running" || task.status === "paused" ? (
                  <div className="mt-2 grid gap-1.5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-3">
                    <span
                      aria-label={`${task.title}进度`}
                      aria-valuemax={100}
                      aria-valuemin={0}
                      aria-valuenow={task.progress}
                      className="h-1.5 overflow-hidden rounded-full bg-[var(--sh-line-subtle)]"
                      role="progressbar"
                    >
                      <span
                        className="block h-full rounded-full bg-[var(--sh-brand-500)]"
                        style={{ width: `${String(task.progress)}%` }}
                      />
                    </span>
                    <span className="text-xs text-[var(--sh-ink-muted)]">
                      当前阶段：{task.status === "paused" ? "已暂停，可随时继续" : task.stage}
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="mt-3 flex flex-wrap justify-end gap-2 border-t border-[var(--sh-line-subtle)] pt-2 md:mt-0 md:border-0 md:pt-0">
                {task.status === "partially_completed" ? (
                  <Button
                    onClick={() =>
                      updateMockTask(task.id, {
                        detail: "失败图片已开始重新处理，其余已完成内容保持不变",
                        progress: 0,
                        retry_count: task.retry_count + 1,
                        stage: "等待重新处理",
                        status: "queued",
                      })
                    }
                    size="sm"
                    variant="secondary"
                  >
                    <RotateCcw aria-hidden="true" />
                    重新处理未完成内容
                  </Button>
                ) : task.status === "running" || task.status === "paused" ? (
                  <Button
                    onClick={() =>
                      updateMockTask(task.id, {
                        status: task.status === "paused" ? "running" : "paused",
                      })
                    }
                    size="sm"
                    variant="quiet"
                  >
                    <PauseCircle aria-hidden="true" />
                    {task.status === "paused" ? "继续" : "暂停"}
                  </Button>
                ) : task.status === "review_required" && task.project_id ? (
                  <Button asChild size="sm">
                    <Link to={confirmationTarget}>去确认</Link>
                  </Button>
                ) : task.status === "queued" ? (
                  <span className="rounded-full bg-[var(--sh-brand-50)] px-3 py-1.5 text-xs font-medium text-[var(--sh-brand-700)]">
                    已进入等待处理
                  </span>
                ) : (
                  <span className="text-xs text-[var(--sh-ink-muted)]">当前无需操作</span>
                )}
              </div>
            </article>
          );
        })}
        {tasks.length === 0 ? (
          <p className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)]">
            当前筛选下没有任务。
          </p>
        ) : null}
      </div>
    </div>
  );
}
