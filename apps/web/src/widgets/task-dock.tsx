import { useState } from "react";
import { ChevronDown, ChevronUp, ListChecks } from "lucide-react";
import type { Task } from "@/shared/api/types";
import { taskTitle } from "@/features/tasks";
import { formatRelativeTime } from "@/shared/lib/format";
import { isTaskActive, type TaskStatus } from "@/shared/lib/status";
import { Button, Progress, TaskStatusBadge } from "@/shared/ui";

/**
 * 任务坞（工作台底部）：收起 48px / 展开 260px。
 * 展示本课时相关任务的实时进度，支持取消与重试。
 */
export function TaskDock({
  tasks,
  onCancel,
  onRetry,
}: {
  tasks: Task[];
  onCancel: (taskId: string) => void;
  onRetry: (taskId: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const active = tasks.filter((task) => isTaskActive(task.status as TaskStatus));
  const recent = tasks.slice(0, 8);

  return (
    <section
      className="shrink-0 border-t border-line bg-surface-1"
      style={{ height: expanded ? 260 : 48 }}
      aria-label="任务坞"
    >
      <button
        type="button"
        className="flex h-12 w-full items-center gap-2 px-4 text-sm text-ink-1 hover:bg-surface-hover"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <ListChecks className="size-4 text-ink-2" aria-hidden />
        任务
        {active.length > 0 ? (
          <span className="rounded-full bg-running-surface px-2 py-0.5 text-xs font-medium text-running">
            {active.length} 个进行中
          </span>
        ) : (
          <span className="text-xs text-ink-muted">暂无进行中任务</span>
        )}
        {active[0] ? (
          <span className="ml-2 hidden min-w-0 flex-1 items-center gap-2 md:flex">
            <span className="truncate text-xs text-ink-2">{taskTitle(active[0])}</span>
            <Progress className="w-40" value={active[0].progress_percent} />
            <span className="text-xs tabular-nums text-ink-muted">{Math.round(active[0].progress_percent)}%</span>
          </span>
        ) : null}
        {expanded ? (
          <ChevronDown className="ml-auto size-4 text-ink-muted" aria-hidden />
        ) : (
          <ChevronUp className="ml-auto size-4 text-ink-muted" aria-hidden />
        )}
      </button>
      {expanded ? (
        <ul className="h-[212px] overflow-y-auto px-4 pb-3">
          {recent.length === 0 ? (
            <li className="py-6 text-center text-sm text-ink-muted">本课时还没有任务记录。</li>
          ) : (
            recent.map((task) => (
              <li key={task.task_id} className="flex items-center gap-3 border-b border-divider py-2.5 last:border-0">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm text-ink-1">{taskTitle(task)}</span>
                    <TaskStatusBadge status={task.status as TaskStatus} />
                  </div>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {task.progress_message ?? ""} · {formatRelativeTime(task.created_at)}
                  </p>
                </div>
                {isTaskActive(task.status as TaskStatus) ? (
                  <>
                    <Progress className="w-28" value={task.progress_percent} />
                    {task.cancellable ? (
                      <Button size="sm" variant="ghost" onClick={() => onCancel(task.task_id)}>
                        取消
                      </Button>
                    ) : null}
                  </>
                ) : task.status === "failed" && task.retryable ? (
                  <Button size="sm" variant="secondary" onClick={() => onRetry(task.task_id)}>
                    重试
                  </Button>
                ) : null}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </section>
  );
}
