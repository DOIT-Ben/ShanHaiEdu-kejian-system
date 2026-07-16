import { useState } from "react";
import { useModelRunDetail, useModelRuns, type ModelRunFilters } from "@/features/admin";
import { formatDuration, formatMinorUnits, formatRelativeTime } from "@/shared/lib/format";
import type { ModelRun } from "@/shared/api/types";
import {
  Badge,
  Drawer,
  DrawerContent,
  EmptyState,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const STATUS_META: Record<ModelRun["status"], { label: string; tone: "neutral" | "running" | "success" | "danger" }> = {
  queued: { label: "排队中", tone: "neutral" },
  running: { label: "运行中", tone: "running" },
  completed: { label: "已完成", tone: "success" },
  failed: { label: "失败", tone: "danger" },
  cancelled: { label: "已取消", tone: "neutral" },
};

const CAPABILITIES = ["text_generation", "image_generation", "video_generation", "tts", "pptx_render"];

function RunDetailDrawer({ runId, onClose }: { runId: string | null; onClose: () => void }) {
  const detail = useModelRunDetail(runId);
  const data = detail.data;
  return (
    <Drawer open={runId !== null} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent title="运行详情">
        {detail.isPending ? (
          <div className="space-y-3">
            <Skeleton className="h-24" />
            <Skeleton className="h-40" />
          </div>
        ) : detail.isError ? (
          <AppErrorPanel error={detail.error} title="详情加载失败" onRetry={() => void detail.refetch()} />
        ) : data ? (
          <div className="space-y-4 text-sm">
            <dl className="space-y-1.5">
              {[
                ["运行 ID", <code key="id" className="font-mono text-xs">{data.run.model_run_id}</code>],
                ["能力", data.run.capability],
                ["模型", `${data.run.model_name ?? data.run.model_id}（${data.run.provider_name ?? data.run.provider_id}）`],
                ["状态", STATUS_META[data.run.status].label],
                ["耗时", data.run.duration_ms ? formatDuration(data.run.duration_ms) : "—"],
                [
                  "费用",
                  data.run.actual_cost_minor_units !== undefined
                    ? formatMinorUnits(data.run.actual_cost_minor_units)
                    : data.run.estimated_cost_minor_units !== undefined
                      ? `预计 ${formatMinorUnits(data.run.estimated_cost_minor_units)}`
                      : "—",
                ],
                ["发起时间", formatRelativeTime(data.run.created_at)],
              ].map(([label, value]) => (
                <div key={label as string} className="flex justify-between gap-3">
                  <dt className="shrink-0 text-ink-muted">{label}</dt>
                  <dd className="min-w-0 text-right text-ink-1">{value}</dd>
                </div>
              ))}
            </dl>
            {data.input_summary ? (
              <section>
                <h4 className="mb-1 text-xs font-semibold text-ink-muted">输入摘要</h4>
                <p className="rounded-control bg-surface-2 px-3 py-2 text-xs leading-5 text-ink-2">{data.input_summary}</p>
              </section>
            ) : null}
            {data.fallback_chain && data.fallback_chain.length > 0 ? (
              <section>
                <h4 className="mb-1 text-xs font-semibold text-ink-muted">备选链</h4>
                <p className="text-xs text-ink-2">{data.fallback_chain.join(" → ")}</p>
              </section>
            ) : null}
            {data.error ? (
              <section>
                <h4 className="mb-1 text-xs font-semibold text-ink-muted">错误信息</h4>
                <p className="rounded-control bg-danger-surface px-3 py-2 text-xs text-danger">
                  {data.error.message}
                  {data.error.trace_id ? <span className="ml-2 font-mono opacity-70">Trace: {data.error.trace_id}</span> : null}
                </p>
              </section>
            ) : null}
          </div>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
}

/** 模型运行记录页：网关每次调用的用量、成本、状态与详情。 */
export function AdminModelRunsPage() {
  const [filters, setFilters] = useState<ModelRunFilters>({});
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const runs = useModelRuns(filters);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="运行记录" description="模型网关的调用流水，用于用量核对与故障排查。" />
      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={filters.capability ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, capability: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-44" aria-label="按能力筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部能力</SelectItem>
            {CAPABILITIES.map((capability) => (
              <SelectItem key={capability} value={capability}>
                {capability}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filters.status ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-32" aria-label="按状态筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            {Object.entries(STATUS_META).map(([value, meta]) => (
              <SelectItem key={value} value={value}>
                {meta.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {runs.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-12" />
          ))}
        </div>
      ) : runs.isError ? (
        <AppErrorPanel error={runs.error} title="运行记录加载失败" onRetry={() => void runs.refetch()} />
      ) : (runs.data ?? []).length === 0 ? (
        <EmptyState title="暂无运行记录" />
      ) : (
        <ul className="divide-y divide-divider rounded-panel border border-line bg-surface-1">
          {(runs.data ?? []).map((run) => {
            const meta = STATUS_META[run.status];
            return (
              <li key={run.model_run_id}>
                <button
                  type="button"
                  onClick={() => setActiveRunId(run.model_run_id)}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-surface-hover"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-ink-1">
                      {run.model_name ?? run.model_id}
                      <span className="ml-1 text-xs text-ink-muted">（{run.provider_name ?? run.provider_id}）</span>
                    </p>
                    <p className="text-xs text-ink-muted">
                      {run.capability} · {formatRelativeTime(run.created_at)}
                      {run.duration_ms ? ` · ${formatDuration(run.duration_ms)}` : ""}
                    </p>
                  </div>
                  {run.is_fallback ? <Badge tone="warning">备用</Badge> : null}
                  <span className="w-20 text-right text-xs tabular-nums text-ink-2">
                    {run.actual_cost_minor_units !== undefined ? formatMinorUnits(run.actual_cost_minor_units) : "—"}
                  </span>
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <RunDetailDrawer runId={activeRunId} onClose={() => setActiveRunId(null)} />
    </div>
  );
}
