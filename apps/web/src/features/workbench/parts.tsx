import { type ReactNode, useState } from "react";
import { CircleStop, Download, RefreshCcw, TriangleAlert } from "lucide-react";
import type { GenerationJob, GenerationResult, NodeRun } from "@/shared/api";
import { useCancelJob, useNodeTransition } from "@/features/node-runs";
import { useDownloadResult } from "@/features/save-to-project";
import { NodeStatusBadge, Button, Spinner, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

/** 画布头（05 FocusPageHeader）：当前要做 + 唯一主操作。 */
export function StepScaffold({
  title,
  description,
  status,
  primaryAction,
  secondaryActions,
  children,
}: {
  title: string;
  description?: ReactNode;
  status?: string | null;
  primaryAction?: ReactNode;
  secondaryActions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-line-subtle bg-surface px-6 py-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2.5">
            <h1 className="truncate text-lg font-semibold text-ink-strong">当前要做：{title}</h1>
            {status ? <NodeStatusBadge status={status} /> : null}
          </div>
          {description ? <p className="mt-0.5 text-sm text-ink-muted">{description}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {secondaryActions}
          {primaryAction}
        </div>
      </header>
      <div className="flex-1 px-6 py-6">{children}</div>
    </div>
  );
}

/** 生成中面板：真实阶段名，无假百分比；可取消。 */
export function RunningPanel({ job, label }: { job: GenerationJob | null; label: string }) {
  const cancel = useCancelJob();
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-lg border border-line-subtle bg-surface p-10 text-center shadow-card">
      <Spinner className="size-8 text-brand-500" />
      <div>
        <p className="text-base font-medium text-ink-strong">{label}</p>
        <p className="mt-1 text-sm text-ink-muted">
          {job?.phase_label ?? "排队中"}
          {job && job.total_items != null
            ? ` · 已完成 ${job.completed_items ?? 0}/${job.total_items}`
            : ""}
        </p>
        <p className="mt-2 text-xs text-ink-faint">可以先去做别的，完成后这里会自动更新。</p>
      </div>
      {job ? (
        <Button
          variant="outline"
          size="sm"
          loading={cancel.isPending}
          onClick={() =>
            cancel.mutate(job.id, {
              onSuccess: () => toast({ tone: "info", title: "正在停止", description: "已提交停止请求。" }),
              onError: (error) => toast({ tone: "danger", title: "停止失败", description: error.message }),
            })
          }
        >
          <CircleStop className="size-4" aria-hidden />
          停止生成
        </Button>
      ) : null}
    </div>
  );
}

/** stale 提醒：内容已变化，建议更新；可保持当前版本。 */
export function StaleBanner({ nodeRun }: { nodeRun: NodeRun }) {
  const transition = useNodeTransition(nodeRun.id);
  const reason = nodeRun.stale_reason;
  return (
    <div className="mb-5 flex flex-wrap items-center gap-3 rounded-lg border border-warning-200 bg-warning-50 p-4">
      <TriangleAlert className="size-5 shrink-0 text-warning" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink-strong">内容已变化，建议更新</p>
        <p className="mt-0.5 text-sm text-ink">
          {reason?.message ?? "上游内容已更新，当前结果可能不再匹配。"}
        </p>
      </div>
      <Button
        variant="outline"
        size="sm"
        loading={transition.isPending}
        onClick={() =>
          transition.mutate(
            { action: "keep_current_version" },
            {
              onSuccess: () => toast({ tone: "success", title: "已保持当前版本" }),
              onError: (error) => toast({ tone: "danger", title: "操作失败", description: error.message }),
            },
          )
        }
      >
        保持当前版本
      </Button>
    </div>
  );
}

/** 候选查看器（05 CandidateViewer）：大图 + 缩略条 + 每候选操作。 */
export function CandidateGallery({
  results,
  renderActions,
  mediaKind = "image",
  emptyHint = "还没有候选结果。",
}: {
  results: GenerationResult[];
  renderActions?: (result: GenerationResult) => ReactNode;
  mediaKind?: "image" | "video";
  emptyHint?: string;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const download = useDownloadResult();
  const active = results.find((r) => r.id === activeId) ?? results[0] ?? null;

  if (results.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line bg-surface-soft p-10 text-center text-sm text-ink-muted">
        {emptyHint}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {active ? (
        <figure className="overflow-hidden rounded-lg border border-line-subtle bg-surface shadow-card">
          <div className={cn("flex items-center justify-center", mediaKind === "video" && "sh-player-surface")}>
            {active.preview_url ? (
              <img
                src={active.preview_url}
                alt={`候选：${active.item_key}`}
                className="max-h-[52vh] w-full object-contain"
              />
            ) : (
              <div className="flex h-64 items-center justify-center text-ink-faint">暂无预览</div>
            )}
          </div>
          <figcaption className="flex flex-wrap items-center gap-2 border-t border-line-subtle px-4 py-3">
            <span className="text-sm text-ink-muted">
              {active.technical_check === "failed" ? (
                <span className="inline-flex items-center gap-1 text-danger">
                  <TriangleAlert className="size-4" aria-hidden />
                  质量检查未通过{active.technical_check_detail ? `：${active.technical_check_detail}` : ""}
                </span>
              ) : active.duration_seconds ? (
                `时长 ${active.duration_seconds} 秒`
              ) : (
                "质量检查通过"
              )}
            </span>
            <span className="ml-auto flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                loading={download.isPending}
                onClick={() =>
                  download.mutate(active.id, {
                    onSuccess: (data) => {
                      window.open(data.url, "_blank", "noopener");
                    },
                    onError: (error) => toast({ tone: "danger", title: "下载失败", description: error.message }),
                  })
                }
              >
                <Download className="size-4" aria-hidden />
                仅下载
              </Button>
              {renderActions?.(active)}
            </span>
          </figcaption>
        </figure>
      ) : null}
      {results.length > 1 ? (
        <ul className="flex gap-2 overflow-x-auto pb-1" role="listbox" aria-label="候选列表">
          {results.map((result, index) => (
            <li key={result.id}>
              <button
                type="button"
                role="option"
                aria-selected={result.id === active?.id}
                onClick={() => setActiveId(result.id)}
                className={cn(
                  "block h-20 w-32 overflow-hidden rounded-md border-2 transition-colors duration-150",
                  result.id === active?.id ? "border-brand-500" : "border-transparent hover:border-line-strong",
                )}
              >
                {result.preview_url ? (
                  <img src={result.preview_url} alt={`候选 ${index + 1}`} className="size-full object-cover" />
                ) : (
                  <span className="flex size-full items-center justify-center bg-surface-soft text-xs text-ink-faint">
                    候选 {index + 1}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** 失败面板：错误信息 + 重试。 */
export function FailedPanel({
  message,
  onRetry,
  retrying,
}: {
  message: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-lg border border-danger-200 bg-danger-50/50 p-10 text-center">
      <TriangleAlert className="size-8 text-danger" aria-hidden />
      <div>
        <p className="text-base font-medium text-ink-strong">生成失败</p>
        <p className="mt-1 text-sm text-ink">{message}</p>
      </div>
      <Button onClick={onRetry} loading={retrying} loadingText="正在重试…">
        <RefreshCcw className="size-4" aria-hidden />
        重试
      </Button>
    </div>
  );
}
