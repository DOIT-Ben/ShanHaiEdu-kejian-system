import { useState } from "react";
import { GitBranch } from "lucide-react";
import { useWorkflowDetail, useWorkflows } from "@/features/admin";
import { NODE_GROUPS } from "@/entities/workflow/nodes";
import { formatRelativeTime } from "@/shared/lib/format";
import { Badge, Drawer, DrawerContent, EmptyState, PageHeader, Skeleton } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const STATUS_META: Record<string, { label: string; tone: "neutral" | "success" | "warning" }> = {
  draft: { label: "草稿", tone: "neutral" },
  published: { label: "已发布", tone: "success" },
  deprecated: { label: "已废弃", tone: "warning" },
};

function WorkflowDetailDrawer({ workflowId, onClose }: { workflowId: string | null; onClose: () => void }) {
  const detail = useWorkflowDetail(workflowId ?? "");
  const data = detail.data;
  return (
    <Drawer open={workflowId !== null} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent title={data ? `${data.workflow.name} ${data.workflow.version}` : "工作流详情"}>
        {detail.isPending ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-10" />
            ))}
          </div>
        ) : detail.isError ? (
          <AppErrorPanel error={detail.error} title="工作流详情加载失败" onRetry={() => void detail.refetch()} />
        ) : data ? (
          <div className="space-y-4">
            {NODE_GROUPS.map((group) => {
              const nodes = data.nodes.filter((node) => node.group === group);
              if (nodes.length === 0) return null;
              return (
                <section key={group}>
                  <h4 className="mb-1.5 text-xs font-semibold text-ink-muted">{group}</h4>
                  <ol className="space-y-1">
                    {nodes.map((node) => (
                      <li key={node.node_key} className="rounded-control border border-line px-3 py-2">
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-ink-1">{node.title}</span>
                          {node.skippable ? <Badge tone="neutral">可跳过</Badge> : null}
                          {node.capability ? <span className="text-[10px] text-ink-muted">{node.capability}</span> : null}
                        </div>
                        {(node.depends_on ?? []).length > 0 ? (
                          <p className="mt-0.5 text-xs text-ink-muted">依赖：{(node.depends_on ?? []).join("、")}</p>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                </section>
              );
            })}
          </div>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
}

/** 工作流模板页：版本列表 + 节点结构查看。 */
export function AdminWorkflowsPage() {
  const workflows = useWorkflows();
  const [activeId, setActiveId] = useState<string | null>(null);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="工作流模板" description="课时制作流程的版本管理；项目创建时绑定当前发布版本。" />

      {workflows.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : workflows.isError ? (
        <AppErrorPanel error={workflows.error} title="工作流加载失败" onRetry={() => void workflows.refetch()} />
      ) : (workflows.data ?? []).length === 0 ? (
        <EmptyState icon={<GitBranch className="size-8" aria-hidden />} title="暂无工作流模板" />
      ) : (
        <ul className="space-y-2">
          {(workflows.data ?? []).map((workflow) => {
            const status = STATUS_META[workflow.status] ?? STATUS_META.draft;
            return (
              <li key={`${workflow.workflow_id}-${workflow.version}`}>
                <button
                  type="button"
                  onClick={() => setActiveId(workflow.workflow_id)}
                  className="flex w-full items-center gap-3 rounded-card border border-line bg-surface-1 px-4 py-3 text-left transition-colors hover:bg-surface-hover"
                >
                  <GitBranch className="size-4 shrink-0 text-ink-2" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink-1">
                      {workflow.name} <span className="text-xs text-ink-muted">{workflow.version}</span>
                    </p>
                    <p className="text-xs text-ink-muted">
                      {workflow.node_count} 个节点 · {workflow.bound_project_count ?? 0} 个项目使用
                      {workflow.published_at ? ` · 发布于 ${formatRelativeTime(workflow.published_at)}` : ""}
                    </p>
                  </div>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <WorkflowDetailDrawer workflowId={activeId} onClose={() => setActiveId(null)} />
    </div>
  );
}
