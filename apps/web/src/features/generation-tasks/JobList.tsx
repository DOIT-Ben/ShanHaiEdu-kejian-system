import { Link } from "react-router";
import { CircleStop, RefreshCcw } from "lucide-react";
import type { GenerationJob } from "@/shared/api";
import { useCancelJob, useRetryJob } from "@/features/node-runs";
import { formatRelativeTime } from "@/shared/lib/format";
import { isTaskActive } from "@/shared/lib/status";
import { Button, EmptyState, Spinner, TaskStatusBadge, toast } from "@/shared/ui";

/** 任务列表（05 TaskStatusBar 的完整形态）：真实阶段与计数，失败可重试、进行中可停止。 */
export function JobList({ jobs, emptyHint }: { jobs: GenerationJob[]; emptyHint: string }) {
  const cancel = useCancelJob();
  const retry = useRetryJob();

  if (jobs.length === 0) {
    return <EmptyState title="没有任务" description={emptyHint} />;
  }

  return (
    <ul className="space-y-3">
      {jobs.map((job) => {
        const active = isTaskActive(job.status);
        const failedItems = job.failed_item_keys ?? [];
        return (
          <li
            key={job.id}
            className="flex flex-wrap items-center gap-3 rounded-lg border border-line-subtle bg-surface p-4 shadow-card"
          >
            {active ? <Spinner className="size-4 text-brand-500" /> : null}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate text-sm font-medium text-ink-strong">{job.title}</p>
                <TaskStatusBadge status={job.status} />
              </div>
              <p className="mt-0.5 text-xs text-ink-muted">
                {job.phase_label ? `${job.phase_label} · ` : ""}
                {job.total_items != null ? `已完成 ${job.completed_items ?? 0}/${job.total_items} · ` : ""}
                {formatRelativeTime(job.updated_at ?? job.created_at)}
              </p>
              {job.status === "failed" || job.status === "partially_completed" ? (
                <p className="mt-1 text-xs text-danger">
                  {job.error?.message ?? "部分内容生成失败。"}
                  {failedItems.length > 0 ? `（${failedItems.length} 项失败）` : ""}
                </p>
              ) : null}
            </div>
            <span className="flex shrink-0 items-center gap-2">
              {(job.status === "failed" || job.status === "partially_completed") && job.error?.retryable !== false ? (
                <Button
                  variant="outline"
                  size="sm"
                  loading={retry.isPending}
                  onClick={() =>
                    retry.mutate(
                      { jobId: job.id, itemKeys: failedItems.length > 0 ? failedItems : undefined },
                      {
                        onSuccess: () =>
                          toast({
                            tone: "info",
                            title: "开始重试",
                            description: failedItems.length > 0 ? "只重试失败的部分。" : undefined,
                          }),
                        onError: (error) => toast({ tone: "danger", title: "无法重试", description: error.message }),
                      },
                    )
                  }
                >
                  <RefreshCcw className="size-4" aria-hidden />
                  {failedItems.length > 0 ? "重试失败部分" : "重试"}
                </Button>
              ) : null}
              {active && job.status !== "cancel_requested" ? (
                <Button
                  variant="ghost"
                  size="sm"
                  loading={cancel.isPending}
                  onClick={() =>
                    cancel.mutate(job.id, {
                      onError: (error) => toast({ tone: "danger", title: "停止失败", description: error.message }),
                    })
                  }
                >
                  <CircleStop className="size-4" aria-hidden />
                  停止
                </Button>
              ) : null}
              {contextUrl(job) ? (
                <Button variant="ghost" size="sm" asChild>
                  <Link to={contextUrl(job)!}>查看位置</Link>
                </Button>
              ) : null}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** 任务来源定位：批次 → 创作中心；课时 → 课时工作台；项目 → 项目总览。 */
function contextUrl(job: GenerationJob): string | null {
  if (job.batch_id) return `/app/creation/batches/${job.batch_id}`;
  if (job.project_id && job.lesson_id) return `/app/projects/${job.project_id}/lessons/${job.lesson_id}`;
  if (job.project_id) return `/app/projects/${job.project_id}`;
  return null;
}
