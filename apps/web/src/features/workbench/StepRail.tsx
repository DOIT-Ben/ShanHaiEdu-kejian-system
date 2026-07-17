import { NavLink } from "react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { STEP_GROUPS, STEPS, type StepDefinition } from "@/entities/workflow";
import type { Lesson, NodeRun } from "@/shared/api";
import { getNodeStatusMeta } from "@/shared/lib/status";
import { cn } from "@/shared/lib/cn";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/shared/ui";

/**
 * 左侧流程栏（02 §4）：教师行动语言分组；只显示状态点与文字，
 * 不用工程术语。禁用分支置灰但可见（disabled ≠ skipped）。
 */
export function StepRail({
  projectId,
  lesson,
  nodeRuns,
  collapsed,
  onToggle,
}: {
  projectId: string;
  lesson: Lesson;
  nodeRuns: NodeRun[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  const nodeByKey = new Map(nodeRuns.map((run) => [run.node_key, run]));

  const stepState = (step: StepDefinition): { status: string | null; disabled: boolean } => {
    if (step.kind === "link") return { status: null, disabled: false };
    const run = step.nodeKey ? nodeByKey.get(step.nodeKey) : undefined;
    if (!run) return { status: null, disabled: false };
    return { status: run.status, disabled: run.status === "disabled" };
  };

  const linkTarget = (step: StepDefinition): string => {
    if (step.key === "textbook" || step.key === "lesson-division") {
      return `/app/projects/${projectId}/materials`;
    }
    if (step.key === "download") {
      return `/app/projects/${projectId}/delivery`;
    }
    return `/app/projects/${projectId}/lessons/${lesson.id}/work/${step.key}`;
  };

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-r border-line-subtle bg-surface transition-[width] duration-200",
        collapsed ? "w-12" : "w-[var(--sh-workbench-rail-width)]",
      )}
      aria-label="课时流程"
    >
      <div className={cn("flex items-center border-b border-line-subtle py-2", collapsed ? "justify-center px-1" : "justify-between px-3")}>
        {!collapsed ? <span className="truncate text-xs font-medium text-ink-muted">{lesson.title}</span> : null}
        <button
          type="button"
          onClick={onToggle}
          aria-label={collapsed ? "展开流程栏" : "收起流程栏"}
          className="flex size-7 items-center justify-center rounded-md text-ink-muted transition-colors duration-150 hover:bg-surface-soft hover:text-ink-strong"
        >
          {collapsed ? <ChevronRight className="size-4" aria-hidden /> : <ChevronLeft className="size-4" aria-hidden />}
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {STEP_GROUPS.map((group) => {
          const steps = STEPS.filter((step) => step.group === group.key);
          return (
            <div key={group.key} className="mb-1.5">
              {!collapsed ? (
                <p className="px-3 pb-1 pt-2 text-xs font-semibold text-ink-faint">{group.label}</p>
              ) : (
                <div className="mx-3 my-2 border-t border-line-subtle" aria-hidden />
              )}
              <ul>
                {steps.map((step) => {
                  const { status, disabled } = stepState(step);
                  const meta = status ? getNodeStatusMeta(status) : null;
                  const item = (
                    <NavLink
                      to={linkTarget(step)}
                      end
                      aria-disabled={disabled}
                      onClick={(event) => {
                        if (disabled) event.preventDefault();
                      }}
                      className={({ isActive }) =>
                        cn(
                          "mx-2 flex items-center gap-2.5 rounded-md py-2 text-sm transition-colors duration-150",
                          collapsed ? "justify-center px-0" : "px-2.5",
                          disabled
                            ? "cursor-not-allowed text-ink-faint"
                            : isActive
                              ? "bg-brand-50 font-medium text-brand-600"
                              : "text-ink hover:bg-surface-soft hover:text-ink-strong",
                        )
                      }
                    >
                      <span
                        aria-hidden
                        className={cn("size-2 shrink-0 rounded-full", meta ? DOT_CLASSES[meta.tone] : "bg-line-strong")}
                      />
                      {!collapsed ? (
                        <>
                          <span className="min-w-0 flex-1 truncate">{step.label}</span>
                          {meta && (status === "review_required" || status === "stale" || status === "failed") ? (
                            <span className={cn("shrink-0 text-xs", meta.tone === "danger" ? "text-danger" : "text-warning")}>
                              {meta.label}
                            </span>
                          ) : null}
                        </>
                      ) : null}
                    </NavLink>
                  );
                  return (
                    <li key={step.key}>
                      {collapsed ? (
                        <Tooltip>
                          <TooltipTrigger asChild>{item}</TooltipTrigger>
                          <TooltipContent side="right">
                            {step.label}
                            {meta ? ` · ${meta.label}` : ""}
                            {disabled ? "（未启用）" : ""}
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        item
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

const DOT_CLASSES: Record<string, string> = {
  neutral: "bg-line-strong",
  brand: "bg-brand-500",
  running: "bg-brand-500 animate-pulse",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
};
