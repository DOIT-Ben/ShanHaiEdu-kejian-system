import { Link } from "react-router";
import { useModelRuns, useUsageOverview } from "@/features/admin";
import { formatDateTime, formatDuration, formatMinorUnits } from "@/shared/lib/format";
import { Badge, PageHeader, Panel, PanelBody, PanelHeader, Skeleton } from "@/shared/ui";

const RUN_STATUS_META: Record<string, { label: string; tone: "success" | "danger" | "running" }> = {
  succeeded: { label: "成功", tone: "success" },
  failed: { label: "失败", tone: "danger" },
  running: { label: "进行中", tone: "running" },
};

/** 运行与费用（04 §2.5）：每日用量、异常提醒、调用记录。 */
export default function AdminUsagePage() {
  const { data: usage, isPending } = useUsageOverview();
  const { data: runs } = useModelRuns();

  if (isPending || !usage) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const maxCost = Math.max(...usage.daily.map((d) => d.cost_minor_units), 1);

  return (
    <div>
      <PageHeader title="运行与费用" description="每天的调用量与费用走势，以及需要关注的异常。" />

      {usage.alerts.length > 0 ? (
        <div className="mt-6 space-y-2">
          {usage.alerts.map((alert, index) => (
            <div
              key={index}
              className="flex items-center gap-3 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-ink"
              role="alert"
            >
              <span className="flex-1">{alert.message}</span>
              {alert.action_url ? (
                <Link to={alert.action_url} className="shrink-0 font-medium text-brand-600 hover:underline">
                  去处理
                </Link>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <Panel className="mt-6">
        <PanelHeader title="近 14 天费用" />
        <PanelBody>
          <div className="flex items-end gap-1.5" role="img" aria-label="每日费用柱状图">
            {usage.daily.map((day) => (
              <div key={day.date} className="group flex min-w-0 flex-1 flex-col items-center gap-1">
                <span className="text-[10px] tabular-nums text-ink-faint opacity-0 transition-opacity duration-150 group-hover:opacity-100">
                  {formatMinorUnits(day.cost_minor_units)}
                </span>
                <div
                  className="w-full rounded-t bg-brand-200 transition-colors duration-150 group-hover:bg-brand-400"
                  style={{ height: `${Math.max(6, Math.round((day.cost_minor_units / maxCost) * 120))}px` }}
                  title={`${day.date}：${formatMinorUnits(day.cost_minor_units)}，${day.run_count} 次调用${day.failed_count ? `，失败 ${day.failed_count}` : ""}`}
                />
                <span className="truncate text-[10px] text-ink-faint">{day.date.slice(5)}</span>
              </div>
            ))}
          </div>
        </PanelBody>
      </Panel>

      <Panel className="mt-6">
        <PanelHeader title="模型调用记录" description="每一次模型调用的能力、供应商、耗时与费用。" />
        <PanelBody className="p-0">
          <ul className="divide-y divide-line-subtle">
            {(runs ?? []).map((run) => {
              const meta = RUN_STATUS_META[run.status] ?? { label: run.status, tone: "running" as const };
              return (
                <li key={run.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {run.capability} · {run.provider_name}
                    {run.model_name ? ` · ${run.model_name}` : ""}
                    {run.project_title ? `（${run.project_title}）` : ""}
                  </span>
                  {run.error_code ? <span className="font-mono text-xs text-danger">{run.error_code}</span> : null}
                  <span className="text-xs tabular-nums text-ink-muted">
                    {run.duration_ms != null ? formatDuration(run.duration_ms) : "—"}
                  </span>
                  <span className="w-20 text-right text-xs tabular-nums text-ink-muted">
                    {run.cost_minor_units != null ? formatMinorUnits(run.cost_minor_units) : "—"}
                  </span>
                  <span className="text-xs text-ink-faint">{formatDateTime(run.started_at)}</span>
                </li>
              );
            })}
          </ul>
        </PanelBody>
      </Panel>
    </div>
  );
}
