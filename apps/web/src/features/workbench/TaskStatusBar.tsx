import { Link } from "react-router";
import { CircleStop } from "lucide-react";
import { useJobs, useEventChannelStore, CONNECTION_MODE_LABELS } from "@/features/generation-tasks";
import { useCancelJob } from "@/features/node-runs";
import { isTaskActive } from "@/shared/lib/status";
import { Button, Spinner, TaskStatusBadge, toast } from "@/shared/ui";

/** 底部任务条（05 TaskStatusBar）：项目内进行中任务 + 实时通道状态。 */
export function TaskStatusBar({ projectId }: { projectId: string }) {
  const { data: jobs } = useJobs({ projectId, active: true });
  const cancel = useCancelJob();
  const mode = useEventChannelStore((s) => s.mode);
  const notice = CONNECTION_MODE_LABELS[mode];
  const active = (jobs ?? []).filter((job) => isTaskActive(job.status));

  if (active.length === 0 && !notice) return null;

  return (
    <div className="flex h-11 shrink-0 items-center gap-3 border-t border-line-subtle bg-surface px-4 text-sm">
      {active.length > 0 ? (
        <>
          <Spinner className="size-4 text-brand-500" />
          <span className="min-w-0 truncate text-ink">
            {active[0].title}
            {active[0].phase_label ? ` · ${active[0].phase_label}` : ""}
            {active[0].total_items != null
              ? `（${active[0].completed_items ?? 0}/${active[0].total_items}）`
              : ""}
          </span>
          <TaskStatusBadge status={active[0].status} />
          {active.length > 1 ? (
            <span className="text-xs text-ink-muted">等 {active.length} 个任务</span>
          ) : null}
          <span className="ml-auto flex items-center gap-2">
            {notice ? <span className="text-xs text-warning">{notice}</span> : null}
            <Button
              variant="ghost"
              size="sm"
              loading={cancel.isPending}
              onClick={() =>
                cancel.mutate(active[0].id, {
                  onError: (error) => toast({ tone: "danger", title: "停止失败", description: error.message }),
                })
              }
            >
              <CircleStop className="size-4" aria-hidden />
              停止
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link to={`/app/projects/${projectId}/tasks`}>全部任务</Link>
            </Button>
          </span>
        </>
      ) : (
        <span className="ml-auto text-xs text-warning">{notice}</span>
      )}
    </div>
  );
}
