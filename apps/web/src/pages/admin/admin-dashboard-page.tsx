import { Link } from "react-router";
import { Activity, AlertTriangle, CircleDollarSign, Timer } from "lucide-react";
import { useGatewayOverview } from "@/features/admin";
import { formatDuration, formatMinorUnits, formatPercent, formatRelativeTime } from "@/shared/lib/format";
import { Badge, EmptyState, PageHeader, Panel, PanelBody, PanelHeader, Skeleton } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const HEALTH_META: Record<string, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  healthy: { label: "正常", tone: "success" },
  degraded: { label: "降级", tone: "warning" },
  unavailable: { label: "不可用", tone: "danger" },
  unknown: { label: "未知", tone: "neutral" },
};

/** 管理仪表盘：今日调用统计 / 服务健康 / 降级提醒 / 失败运行。 */
export function AdminDashboardPage() {
  const overview = useGatewayOverview();

  if (overview.isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-9 w-48" />
        <div className="grid gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }
  if (overview.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={overview.error} title="仪表盘加载失败" onRetry={() => void overview.refetch()} />
      </div>
    );
  }

  const data = overview.data;
  const stats = [
    { icon: Activity, label: "今日调用次数", value: String(data.today.run_count) },
    { icon: CircleDollarSign, label: "今日费用", value: formatMinorUnits(data.today.cost_minor_units) },
    { icon: Timer, label: "平均耗时", value: formatDuration(data.today.average_duration_ms) },
    { icon: AlertTriangle, label: "成功率", value: formatPercent(data.today.success_rate_percent) },
  ];

  return (
    <div className="space-y-5 p-6">
      <PageHeader title="仪表盘" description="模型网关运行概况与需要关注的事项。" />

      <div className="grid gap-4 lg:grid-cols-4 md:grid-cols-2">
        {stats.map((stat) => (
          <Panel key={stat.label}>
            <PanelBody className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-card bg-brand-selected text-brand">
                <stat.icon className="size-5" aria-hidden />
              </span>
              <span>
                <span className="block text-xs text-ink-muted">{stat.label}</span>
                <span className="block text-xl font-semibold text-ink-1">{stat.value}</span>
              </span>
            </PanelBody>
          </Panel>
        ))}
      </div>

      {data.degraded.length > 0 ? (
        <div className="rounded-panel border border-warning/40 bg-warning-surface px-5 py-4">
          <p className="flex items-center gap-2 text-sm font-medium text-ink-1">
            <AlertTriangle className="size-4 text-warning" aria-hidden />
            服务降级提醒
          </p>
          <ul className="mt-2 space-y-1 text-sm text-ink-2">
            {data.degraded.map((notice) => (
              <li key={notice.provider_id}>
                <Link to="/admin/model-gateway/providers" className="font-medium text-brand hover:underline">
                  {notice.provider_name}
                </Link>
                ：{notice.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader
            title="服务健康"
            actions={
              <Link to="/admin/model-gateway/providers" className="text-xs font-medium text-brand hover:underline">
                管理 Provider
              </Link>
            }
          />
          <PanelBody>
            <ul className="divide-y divide-divider">
              {data.providers.map((provider) => {
                const health = HEALTH_META[provider.health_status] ?? HEALTH_META.unknown;
                return (
                  <li key={provider.provider_id} className="flex items-center gap-3 py-2.5">
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-1">{provider.name}</span>
                    <span className="text-xs text-ink-muted">{provider.provider_type}</span>
                    {!provider.enabled ? <Badge tone="neutral">已停用</Badge> : null}
                    <Badge tone={health.tone}>{health.label}</Badge>
                  </li>
                );
              })}
            </ul>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader
            title="最近失败的模型调用"
            actions={
              <Link to="/admin/model-gateway/runs" className="text-xs font-medium text-brand hover:underline">
                全部运行记录
              </Link>
            }
          />
          <PanelBody>
            {data.failed_runs.length === 0 ? (
              <EmptyState title="今日暂无失败调用" className="py-8" />
            ) : (
              <ul className="divide-y divide-divider">
                {data.failed_runs.map((run) => (
                  <li key={run.model_run_id} className="flex items-center gap-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink-1">
                        {run.model_name ?? run.model_id}
                        <span className="ml-1 text-xs text-ink-muted">（{run.provider_name ?? run.provider_id}）</span>
                      </p>
                      <p className="text-xs text-ink-muted">
                        {run.capability} · {formatRelativeTime(run.created_at)}
                      </p>
                    </div>
                    {run.is_fallback ? <Badge tone="warning">备用</Badge> : null}
                    <Badge tone="danger">失败</Badge>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="能力主选模型" description="各生成能力当前的默认路由模型。" />
        <PanelBody>
          <ul className="grid gap-2 lg:grid-cols-3 md:grid-cols-2">
            {data.capability_primaries.map((item) => (
              <li key={item.capability} className="rounded-control border border-line px-3 py-2.5">
                <p className="text-xs text-ink-muted">{item.capability}</p>
                <p className="mt-0.5 text-sm font-medium text-ink-1">{item.business_name}</p>
                <p className="text-xs text-ink-muted">{item.provider_name}</p>
              </li>
            ))}
          </ul>
        </PanelBody>
      </Panel>
    </div>
  );
}
