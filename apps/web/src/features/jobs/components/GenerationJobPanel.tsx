import { CheckCircle2, LoaderCircle, RefreshCw, XCircle } from "lucide-react";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";
import { terminalGenerationJobStatuses } from "@/features/jobs/jobStatus";
import { Button } from "@/shared/ui/Button";

type GenerationJobPanelProps = {
  cancelLabel?: string;
  cancelPending?: boolean;
  errorMessage?: string;
  job?: GenerationJobDto;
  loading?: boolean;
  onCancel?: () => void;
  onRefresh?: () => void;
  progressLabel?: string;
  title?: string;
};

function statusTitle(status: GenerationJobDto["status"]) {
  if (status === "succeeded") return "任务已经完成";
  if (status === "failed") return "任务没有完成";
  if (status === "cancelled") return "任务已取消";
  if (status === "cancel_requested") return "正在取消任务";
  return "任务正在处理";
}

export function GenerationJobPanel({
  cancelLabel = "取消任务",
  cancelPending = false,
  errorMessage,
  job,
  loading = false,
  onCancel,
  onRefresh,
  progressLabel = "任务进度",
  title,
}: GenerationJobPanelProps) {
  if (!job) {
    return (
      <div className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
        <p className="text-sm text-[var(--sh-ink-muted)]" role={loading ? "status" : undefined}>
          {loading ? "正在读取任务状态" : "尚未读取到任务。"}
        </p>
        {errorMessage ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {errorMessage}
          </p>
        ) : null}
        {onRefresh ? (
          <Button className="mt-4" onClick={onRefresh} size="sm" variant="secondary">
            <RefreshCw aria-hidden="true" />
            刷新任务状态
          </Button>
        ) : null}
      </div>
    );
  }

  const progress = Math.min(100, Math.max(0, job.progress_percent));
  const terminal = terminalGenerationJobStatuses.has(job.status);
  return (
    <section className="overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]">
      <div className="grid gap-4 p-5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
        <span
          className={`grid size-11 place-items-center rounded-full ${job.status === "succeeded" ? "bg-[var(--sh-success-soft)] text-[var(--sh-success)]" : job.status === "failed" || job.status === "cancelled" ? "bg-[var(--sh-danger-soft)] text-[var(--sh-danger)]" : "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]"}`}
        >
          {job.status === "succeeded" ? (
            <CheckCircle2 aria-hidden="true" />
          ) : job.status === "failed" || job.status === "cancelled" ? (
            <XCircle aria-hidden="true" />
          ) : (
            <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
          )}
        </span>
        <div>
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">
            {title ?? statusTitle(job.status)}
          </h2>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            {job.progress_message || "正在等待最新进度"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {onRefresh ? (
            <Button disabled={loading} onClick={onRefresh} size="sm" variant="secondary">
              <RefreshCw aria-hidden="true" />
              刷新
            </Button>
          ) : null}
          {!terminal && job.status !== "cancel_requested" && onCancel ? (
            <Button disabled={cancelPending} onClick={onCancel} size="sm" variant="secondary">
              {cancelLabel}
            </Button>
          ) : null}
        </div>
      </div>
      <div className="h-2 bg-[var(--sh-surface-soft)]">
        <div
          aria-label={`${progressLabel} ${String(progress)}%`}
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={progress}
          className="h-full bg-[var(--sh-action-primary)]"
          role="progressbar"
          style={{ width: `${String(progress)}%` }}
        />
      </div>
      {job.status === "failed" ? (
        <p
          className="border-t border-[var(--sh-line-subtle)] px-5 py-3 text-sm text-[var(--sh-danger)]"
          role="alert"
        >
          任务没有完成。请刷新状态；如果问题持续，请稍后重试。
        </p>
      ) : null}
      {errorMessage ? (
        <p
          className="border-t border-[var(--sh-line-subtle)] px-5 py-3 text-sm text-[var(--sh-danger)]"
          role="alert"
        >
          {errorMessage}
        </p>
      ) : null}
    </section>
  );
}
