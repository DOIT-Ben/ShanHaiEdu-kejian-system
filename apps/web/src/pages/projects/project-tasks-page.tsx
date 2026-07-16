import { useState } from "react";
import { Link, useOutletContext } from "react-router";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useCancelTask, useProjectTasks, useRetryTask, taskTitle, type TaskFilters } from "@/features/tasks";
import { getNodeDef } from "@/entities/workflow/nodes";
import { formatMinorUnits, formatRelativeTime } from "@/shared/lib/format";
import { isTaskActive, type TaskStatus } from "@/shared/lib/status";
import {
  Button,
  EmptyState,
  PageHeader,
  Progress,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  TaskStatusBadge,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const STATUS_OPTIONS = [
  { value: "all", label: "全部状态" },
  { value: "running", label: "进行中" },
  { value: "queued", label: "排队中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
  { value: "cancelled", label: "已取消" },
];

/** 任务中心页：项目内全部后台任务，支持取消/重试/跳转来源节点。 */
export function ProjectTasksPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const [filters, setFilters] = useState<TaskFilters>({});
  const tasks = useProjectTasks(project.project_id, filters, { refetchInterval: 5000 });
  const cancel = useCancelTask(project.project_id);
  const retry = useRetryTask(project.project_id);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="任务" description="项目内的生成、解析与打包任务；失败任务可在这里重试。" />
      <div className="flex items-center gap-2">
        <Select
          value={filters.status ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-32" aria-label="按状态筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {tasks.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : tasks.isError ? (
        <AppErrorPanel error={tasks.error} title="任务加载失败" onRetry={() => void tasks.refetch()} />
      ) : (tasks.data ?? []).length === 0 ? (
        <EmptyState title="暂无任务" description="发起生成后，任务进度会显示在这里。" />
      ) : (
        <ul className="space-y-2">
          {(tasks.data ?? []).map((task) => {
            const active = isTaskActive(task.status as TaskStatus);
            return (
              <li key={task.task_id} className="rounded-card border border-line bg-surface-1 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-ink-1">{taskTitle(task)}</span>
                      <TaskStatusBadge status={task.status as TaskStatus} />
                    </div>
                    <p className="mt-0.5 text-xs text-ink-muted">
                      {task.lesson_id && task.node_key ? (
                        <Link
                          to={`../lessons/${task.lesson_id}/workbench/${task.node_key}`}
                          className="text-brand hover:underline"
                        >
                          {getNodeDef(task.node_key)?.title ?? task.node_key}
                        </Link>
                      ) : null}
                      {task.provider_name ? ` · ${task.provider_name}` : ""} · {formatRelativeTime(task.created_at)}
                      {task.actual_cost_minor_units
                        ? ` · 费用 ${formatMinorUnits(task.actual_cost_minor_units)}`
                        : task.estimated_cost_minor_units
                          ? ` · 预计 ${formatMinorUnits(task.estimated_cost_minor_units)}`
                          : ""}
                    </p>
                  </div>
                  {active ? <Progress className="w-32" value={task.progress_percent} /> : null}
                  {active && task.cancellable ? (
                    <Button size="sm" variant="ghost" onClick={() => cancel.mutate(task.task_id)} loading={cancel.isPending}>
                      取消
                    </Button>
                  ) : null}
                  {task.status === "failed" && task.retryable ? (
                    <Button size="sm" variant="secondary" onClick={() => retry.mutate(task.task_id)} loading={retry.isPending}>
                      重试
                    </Button>
                  ) : null}
                </div>
                {task.status === "failed" && task.error ? (
                  <p className="mt-2 rounded-control bg-danger-surface px-3 py-1.5 text-xs text-danger">
                    {task.error.message}
                    {task.error.trace_id ? <span className="ml-2 font-mono text-[10px] opacity-70">Trace: {task.error.trace_id}</span> : null}
                  </p>
                ) : null}
                {task.status === "running" && task.progress_message ? (
                  <p className="mt-1.5 text-xs text-ink-muted">{task.progress_message}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
