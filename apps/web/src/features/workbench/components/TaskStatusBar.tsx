import { CircleAlert, LoaderCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { useMockRuntime } from "@/shared/api/mocks/runtime";

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
    <div className="flex min-h-8 items-center border-t border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 py-1 text-xs text-[var(--sh-ink-muted)]">
      {activeCount > 0 ? (
        <Link
          className="flex items-center gap-1.5 font-medium text-[var(--sh-brand-700)] hover:underline"
          to={`/app/projects/${projectId}/tasks`}
        >
          <LoaderCircle
            aria-hidden="true"
            className="size-3.5 animate-spin text-[var(--sh-brand-500)] motion-reduce:animate-none"
          />
          {activeCount} 项作品正在制作 · 查看任务
        </Link>
      ) : actionCount > 0 ? (
        <Link
          className="flex items-center gap-1.5 font-medium text-[var(--sh-brand-700)] hover:underline"
          to={`/app/projects/${projectId}/tasks`}
        >
          <CircleAlert aria-hidden="true" className="size-3.5 text-[var(--sh-warning)]" />
          {actionCount} 项需要你处理 · 查看任务
        </Link>
      ) : null}
    </div>
  );
}
