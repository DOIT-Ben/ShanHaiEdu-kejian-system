import type { ReactNode } from "react";
import { CheckCircle2, Clock3, History, Loader2, RotateCcw, Sparkles, XCircle } from "lucide-react";
import type { NodeWorkspace, Task } from "@/shared/api/types";
import { formatMinorUnits } from "@/shared/lib/format";
import type { NodeStatus, TaskStatus } from "@/shared/lib/status";
import { Button, EmptyState, ErrorRecoveryPanel, Progress, Spinner } from "@/shared/ui";

/**
 * 输出面板：承载节点产物区的全部运行/结果状态。
 * 覆盖契约要求的 12 种状态：空 / 准备中 / 排队中 / 生成中 / 进度 /
 * 待审核 / 已确认 / 失败 / 可重试 / 已取消 / 部分成功 / 失效。
 * 结果永远驻留面板，不允许只用 Toast 提示。
 */
export interface OutputPanelProps {
  workspace: NodeWorkspace;
  /** 当前活动任务详情（轮询/SSE 驱动）。 */
  task?: Task | null;
  /** 提交运行请求中（任务尚未建立）。 */
  submitting?: boolean;
  onCancelTask?: (taskId: string) => void;
  onRetryTask?: (taskId: string) => void;
  onStartFirstRun?: () => void;
  onConfirmStale?: (versionId: string) => void;
  onRegenerate?: () => void;
  /** 有产物时的内容画布。 */
  children: ReactNode;
}

function TaskProgressCard({ task, onCancel }: { task: Task; onCancel?: (taskId: string) => void }) {
  const status = task.status as TaskStatus;
  const label =
    status === "queued"
      ? "排队中"
      : status === "waiting_provider"
        ? "等待模型服务返回"
        : status === "downloading"
          ? "正在下载生成产物"
          : status === "cancel_requested"
            ? "正在取消"
            : "生成中";
  return (
    <div className="rounded-panel border border-line bg-surface-1 p-6">
      <div className="flex items-center gap-3">
        {status === "queued" ? (
          <Clock3 className="size-5 text-ink-muted" aria-hidden />
        ) : (
          <Loader2 className="size-5 animate-spin text-running" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-1">{label}</p>
          <p className="mt-0.5 text-xs text-ink-2">{task.progress_message ?? "任务正在执行"}</p>
        </div>
        <span className="text-sm font-medium tabular-nums text-ink-2">{Math.round(task.progress_percent)}%</span>
      </div>
      <Progress className="mt-3" value={task.progress_percent} />
      <div className="mt-3 flex items-center justify-between">
        <p className="text-xs text-ink-muted">
          {task.provider_name ? `执行服务：${task.provider_name} · ` : ""}
          {task.estimated_cost_minor_units
            ? `预计费用 ${formatMinorUnits(task.estimated_cost_minor_units)}`
            : "本步骤不产生模型费用"}
        </p>
        {task.cancellable && status !== "cancel_requested" && onCancel ? (
          <Button size="sm" variant="ghost" onClick={() => onCancel(task.task_id)}>
            取消任务
          </Button>
        ) : null}
      </div>
      {status === "cancel_requested" ? (
        <p className="mt-2 text-xs text-warning">正在取消（已发出的模型调用可能仍会计费）。</p>
      ) : null}
    </div>
  );
}

export function OutputPanel({
  workspace,
  task,
  submitting,
  onCancelTask,
  onRetryTask,
  onStartFirstRun,
  onConfirmStale,
  onRegenerate,
  children,
}: OutputPanelProps) {
  const nodeStatus = workspace.node.status as NodeStatus;
  const latest = workspace.artifact_versions[0] ?? null;
  const hasArtifact = workspace.artifact_versions.length > 0;
  const taskActive =
    task && ["queued", "running", "waiting_provider", "downloading", "cancel_requested"].includes(task.status);

  // —— 提交中（任务未建立）
  if (submitting && !taskActive) {
    return (
      <div className="rounded-panel border border-line bg-surface-1 p-6">
        <Spinner label="正在提交生成请求…" />
      </div>
    );
  }

  // —— 排队 / 生成中（含进度）
  if (taskActive && task) {
    return (
      <div className="space-y-4">
        <TaskProgressCard task={task} onCancel={onCancelTask} />
        {hasArtifact ? (
          <div className="rounded-panel border border-line bg-surface-1 p-4">
            <p className="mb-3 flex items-center gap-1.5 text-xs text-ink-muted">
              <History className="size-3.5" aria-hidden />
              下方为上一版结果，生成完成后将产生新版本。
            </p>
            {children}
          </div>
        ) : null}
      </div>
    );
  }

  // —— 失败 / 可重试
  if (nodeStatus === "failed" || task?.status === "failed") {
    const error = task?.error;
    const retryable = Boolean(error?.retryable ?? true);
    return (
      <div className="space-y-4">
        <ErrorRecoveryPanel
          title="生成失败"
          message={error?.message ?? "生成过程中发生错误。"}
          costNote={
            task?.cost_incurred
              ? `本次已产生费用 ${formatMinorUnits(task.actual_cost_minor_units ?? task.estimated_cost_minor_units ?? 0)}。`
              : "本次未产生模型费用。"
          }
          traceId={error?.trace_id}
          actions={
            <>
              {retryable && task && onRetryTask ? (
                <Button size="sm" onClick={() => onRetryTask(task.task_id)}>
                  <RotateCcw className="size-4" aria-hidden />
                  重试
                </Button>
              ) : null}
              {onRegenerate ? (
                <Button size="sm" variant="secondary" onClick={onRegenerate}>
                  调整后重新生成
                </Button>
              ) : null}
            </>
          }
        />
        {hasArtifact ? <div className="rounded-panel border border-line bg-surface-1 p-4">{children}</div> : null}
      </div>
    );
  }

  // —— 已取消
  if (nodeStatus === "cancelled" || task?.status === "cancelled") {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between rounded-panel border border-line bg-surface-2 px-5 py-4">
          <p className="flex items-center gap-2 text-sm text-ink-2">
            <XCircle className="size-4 text-ink-muted" aria-hidden />
            上次生成已取消{task?.cost_incurred ? "（已发出的调用可能计费）" : "，未产生费用"}。
          </p>
          {onRegenerate ? (
            <Button size="sm" variant="secondary" onClick={onRegenerate}>
              重新开始
            </Button>
          ) : null}
        </div>
        {hasArtifact ? <div className="rounded-panel border border-line bg-surface-1 p-4">{children}</div> : null}
      </div>
    );
  }

  // —— 空状态
  if (!hasArtifact) {
    if (nodeStatus === "locked" || nodeStatus === "blocked") {
      return (
        <EmptyState
          title="等待上游步骤完成"
          description={workspace.node.blocker_message ?? "完成依赖的上游步骤后，这里就可以开始生成。"}
        />
      );
    }
    return (
      <EmptyState
        icon={<Sparkles className="size-8" aria-hidden />}
        title="还没有生成结果"
        description="在右侧检查器中确认输入与提示词，然后开始生成。"
        action={
          onStartFirstRun ? (
            <Button size="sm" onClick={onStartFirstRun}>
              开始生成
            </Button>
          ) : undefined
        }
      />
    );
  }

  // —— 有产物：失效 / 部分成功 / 待审核 / 需修改 / 已确认
  const failedValidation = (workspace.validation_results ?? []).filter((v) => !v.passed && v.severity === "error");
  const isPartial = failedValidation.length > 0 && (nodeStatus === "needs_review" || nodeStatus === "revision_required");

  return (
    <div className="space-y-3">
      {nodeStatus === "stale" && latest ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-panel border border-warning/40 bg-warning-surface px-4 py-3">
          <p className="text-sm text-ink-1">
            上游内容已更新，本结果可能失效。
            {latest.stale_reason ? <span className="block text-xs text-ink-2">{latest.stale_reason}</span> : null}
          </p>
          <div className="flex items-center gap-2">
            {onConfirmStale ? (
              <Button size="sm" variant="secondary" onClick={() => onConfirmStale(latest.artifact_version_id)}>
                确认沿用当前结果
              </Button>
            ) : null}
            {onRegenerate ? (
              <Button size="sm" onClick={onRegenerate}>
                重新生成
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
      {isPartial ? (
        <div className="rounded-panel border border-warning/40 bg-warning-surface px-4 py-3">
          <p className="text-sm font-medium text-ink-1">部分内容未完成</p>
          <ul className="mt-1 space-y-0.5 text-xs text-ink-2">
            {failedValidation.map((v) => (
              <li key={v.rule_id}>
                {v.message}
                {v.action ? `（${v.action}）` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {nodeStatus === "approved" ? (
        <p className="flex items-center gap-1.5 text-xs text-success">
          <CheckCircle2 className="size-4" aria-hidden />
          本步骤结果已确认{latest?.approved_at ? "" : ""}，下游步骤已解锁。
        </p>
      ) : null}
      <div className="rounded-panel border border-line bg-surface-1 p-4">{children}</div>
    </div>
  );
}
