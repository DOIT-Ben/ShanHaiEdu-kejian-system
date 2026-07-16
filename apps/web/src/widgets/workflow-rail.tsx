import { Fragment } from "react";
import { ChevronRight } from "lucide-react";
import type { NodeSummary } from "@/shared/api/types";
import { NODE_GROUPS, LESSON_NODES } from "@/entities/workflow/nodes";
import { cn } from "@/shared/lib/cn";
import type { NodeStatus } from "@/shared/lib/status";
import { NodeStatusBadge } from "@/shared/ui";

/**
 * 工作流侧栏（280px）：按阶段分组展示 18 个节点，
 * 状态一目了然；点击切换当前编辑节点。
 */
export function WorkflowRail({
  nodes,
  activeNodeKey,
  onSelect,
}: {
  nodes: NodeSummary[];
  activeNodeKey: string;
  onSelect: (nodeKey: string) => void;
}) {
  const byKey = new Map(nodes.map((node) => [node.node_key, node]));
  return (
    <nav className="flex h-full w-[280px] shrink-0 flex-col overflow-y-auto border-r border-line bg-surface-1" aria-label="课时工作流">
      {NODE_GROUPS.map((group) => {
        const groupNodes = LESSON_NODES.filter((def) => def.group === group && byKey.has(def.key));
        if (groupNodes.length === 0) return null;
        return (
          <Fragment key={group}>
            <p className="sticky top-0 z-10 border-b border-line bg-surface-1 px-4 pb-1.5 pt-3 text-xs font-semibold text-ink-muted">
              {group}
            </p>
            <ul className="px-2 py-1.5">
              {groupNodes.map((def) => {
                const node = byKey.get(def.key)!;
                const active = def.key === activeNodeKey;
                const status = node.status as NodeStatus;
                return (
                  <li key={def.key}>
                    <button
                      type="button"
                      onClick={() => onSelect(def.key)}
                      aria-current={active ? "step" : undefined}
                      className={cn(
                        "group flex w-full items-center gap-2 rounded-control px-2.5 py-2 text-left transition-colors",
                        active ? "bg-brand-selected" : "hover:bg-surface-hover",
                        status === "locked" && !active ? "opacity-60" : "",
                      )}
                    >
                      <span className={cn("min-w-0 flex-1 truncate text-sm", active ? "font-medium text-brand" : "text-ink-1")}>
                        {def.title}
                      </span>
                      <NodeStatusBadge status={status} />
                      <ChevronRight
                        className={cn("size-3.5 shrink-0 text-ink-muted opacity-0 transition-opacity", active ? "opacity-100" : "group-hover:opacity-100")}
                        aria-hidden
                      />
                    </button>
                    {node.status === "running" && typeof node.progress_percent === "number" ? (
                      <div className="mx-2.5 mb-1 h-1 overflow-hidden rounded-full bg-surface-2">
                        <div className="h-full bg-running transition-all" style={{ width: `${node.progress_percent}%` }} />
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </Fragment>
        );
      })}
    </nav>
  );
}
