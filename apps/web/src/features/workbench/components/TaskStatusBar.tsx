import { Link } from "react-router-dom";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export function TaskStatusBar({ projectId }: { projectId: string }) {
  const tasks = useMockRuntime((state) => state.tasks);
  const projectTasks = tasks.filter((task) => task.project_id === projectId);
  const activeCount = projectTasks.filter(
    (task) => task.status === "queued" || task.status === "running" || task.status === "paused",
  ).length;
  const actionCount = projectTasks.filter(
    (task) =>
      task.status === "review_required" ||
      task.status === "failed" ||
      task.status === "partially_completed",
  ).length;
  if (activeCount === 0 && actionCount === 0) return null;

  return (
    <div className="flex min-h-8 shrink-0 items-center border-t border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 py-1 text-xs text-[var(--sh-ink-muted)]">
      {activeCount > 0 ? (
        <Link
          aria-label={`${String(activeCount)} 项作品正在制作 · 查看任务`}
          className="flex items-center gap-1.5 font-medium text-[var(--sh-brand-700)] hover:underline"
          to={`/app/projects/${projectId}/tasks`}
        >
          <StatusBadge label={`${String(activeCount)} 项作品制作中`} status="running" />
          <span>查看任务</span>
        </Link>
      ) : actionCount > 0 ? (
        <Link
          aria-label={`${String(actionCount)} 项需要你处理 · 查看任务`}
          className="flex items-center gap-1.5 font-medium text-[var(--sh-brand-700)] hover:underline"
          to={`/app/projects/${projectId}/tasks`}
        >
          <StatusBadge label={`${String(actionCount)} 项需要处理`} status="review_required" />
          <span>查看任务</span>
        </Link>
      ) : null}
    </div>
  );
}
