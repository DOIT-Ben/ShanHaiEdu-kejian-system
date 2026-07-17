import { useState } from "react";
import { useAdminWorkflow, useAdminWorkflows } from "@/features/admin";
import { formatDateTime, formatMinorUnits } from "@/shared/lib/format";
import { Badge, PageHeader, Panel, PanelBody, PanelHeader, Skeleton } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

/** 工作流管理（04 §2.3）：DAG 只读查看（依赖、确认点、可跳过、预算）。 */
export default function AdminWorkflowsPage() {
  const { data: workflows, isPending } = useAdminWorkflows();
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = activeId ?? workflows?.[0]?.id ?? null;
  const { data: detail } = useAdminWorkflow(active);

  return (
    <div>
      <PageHeader title="工作流" description="定义每个项目的制作步骤与依赖。修改以新版本发布，运行中的项目不受影响。" />
      {isPending ? (
        <Skeleton className="mt-6 h-96 rounded-lg" />
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
          <nav aria-label="工作流列表" className="space-y-2">
            {(workflows ?? []).map((workflow) => (
              <button
                key={workflow.id}
                type="button"
                onClick={() => setActiveId(workflow.id)}
                className={cn(
                  "w-full rounded-lg border p-4 text-left transition-colors duration-150",
                  workflow.id === active
                    ? "border-brand-500 bg-brand-50/60"
                    : "border-line-subtle bg-surface hover:bg-surface-soft",
                )}
              >
                <p className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-medium text-ink-strong">{workflow.title}</span>
                  <Badge tone={workflow.status === "published" ? "success" : "neutral"}>
                    {workflow.status === "published" ? "已发布" : "草稿"}
                  </Badge>
                </p>
                <p className="mt-1 text-xs text-ink-muted">
                  {workflow.node_count} 个节点
                  {workflow.version_no ? ` · 第 ${workflow.version_no} 版` : ""} ·{" "}
                  {formatDateTime(workflow.updated_at)}
                </p>
              </button>
            ))}
          </nav>
          <Panel>
            <PanelHeader
              title={detail?.workflow.title ?? "选择一个工作流"}
              description="节点按依赖顺序展示；含确认点与预算上限。"
            />
            <PanelBody className="p-0">
              {detail ? (
                <ol className="divide-y divide-line-subtle">
                  {detail.nodes.map((node, index) => (
                    <li key={node.node_key} className="flex flex-wrap items-start gap-3 px-5 py-4">
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-surface-soft text-xs font-semibold text-ink">
                        {index + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-strong">
                          {node.title}
                          <span className="font-mono text-xs font-normal text-ink-faint">{node.node_key}</span>
                        </p>
                        <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                          <span>能力：{node.capability}</span>
                          {node.depends_on && node.depends_on.length > 0 ? (
                            <span>依赖：{node.depends_on.join("、")}</span>
                          ) : (
                            <span>无前置依赖</span>
                          )}
                          {node.retry_limit != null ? <span>重试上限 {node.retry_limit}</span> : null}
                          {node.budget_minor_units != null ? (
                            <span>预算 {formatMinorUnits(node.budget_minor_units)}</span>
                          ) : null}
                        </p>
                      </div>
                      <span className="flex shrink-0 gap-1.5">
                        {node.human_gate ? <Badge tone="warning">需老师确认</Badge> : null}
                        {node.skippable ? <Badge tone="neutral">可跳过</Badge> : null}
                      </span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="p-5 text-sm text-ink-muted">左侧选择工作流查看节点。</p>
              )}
            </PanelBody>
          </Panel>
        </div>
      )}
    </div>
  );
}
