import { useEffect, useRef } from "react";
import { NavLink, useLocation, useParams } from "react-router-dom";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { getWorkbenchStepStatus } from "@/features/workbench/lib/stepAccess";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { projectSteps } from "@/shared/data/mockData";
import { cn } from "@/shared/lib/cn";

type ProjectStepNavigationProps = {
  base: string;
  collapsed?: boolean;
  onNavigate?: () => void;
};

function statusLabel(status: WorkflowStatus) {
  if (status === "approved") return "已完成";
  if (status === "review_required") return "待确认";
  if (status === "stale") return "需更新";
  if (status === "ready") return "已准备";
  if (status === "queued" || status === "running") return "制作中";
  if (status === "failed") return "需处理";
  if (status === "paused") return "已暂停";
  if (status === "draft") return "草稿";
  return status === "unknown" ? "待同步" : "未解锁";
}

export function ProjectStepNavigation({
  base,
  collapsed = false,
  onNavigate,
}: ProjectStepNavigationProps) {
  const { lessonId = "", projectId = "" } = useParams();
  const location = useLocation();
  const activeStepRef = useRef<HTMLAnchorElement>(null);
  const runtime = useMockRuntime();
  const currentPath = location.pathname.replace(/\/$/, "");

  useEffect(() => {
    const activeStep = activeStepRef.current;
    const scrollContainer = activeStep?.closest<HTMLElement>("[data-step-scroll-container]");
    if (!activeStep || !scrollContainer) return;
    const itemRect = activeStep.getBoundingClientRect();
    const containerRect = scrollContainer.getBoundingClientRect();
    if (containerRect.height <= 0) return;
    const itemCenter = itemRect.top + itemRect.height / 2;
    const containerCenter = containerRect.top + containerRect.height / 2;
    const reducedMotion =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scrollContainer.scrollTo({
      behavior: reducedMotion ? "auto" : "smooth",
      top: Math.max(0, scrollContainer.scrollTop + itemCenter - containerCenter),
    });
  }, [currentPath]);

  return (
    <nav
      aria-label="课时制作流程"
      className="px-2 pb-[calc((100dvh-var(--sh-topbar-height)-52px)/2)]"
    >
      {projectSteps.map((group) => (
        <div className="mb-5" key={group.group}>
          {!collapsed ? (
            <p className="mb-1 px-3 text-xs font-semibold text-[var(--sh-ink-muted)]">
              {group.group}
            </p>
          ) : null}
          {group.items.map((item) => {
            const status = getWorkbenchStepStatus(runtime, projectId, lessonId, item.key);
            const stepPath = `${base}/${item.key}`;
            return (
              <NavLink
                className={({ isActive }) =>
                  cn(
                    "relative mb-0.5 flex min-h-11 items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 text-sm text-[var(--sh-ink-muted)] transition-colors duration-[var(--sh-duration-fast)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]",
                    isActive &&
                      "bg-[var(--sh-surface-soft)] font-semibold text-[var(--sh-brand-700)] before:absolute before:bottom-2 before:left-0 before:top-2 before:w-[3px] before:rounded-r-full before:bg-[var(--sh-brand-500)]",
                    collapsed && "justify-center px-2",
                  )
                }
                key={item.key}
                onClick={onNavigate}
                ref={currentPath === stepPath ? activeStepRef : undefined}
                title={collapsed ? item.label : undefined}
                to={stepPath}
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className={cn(
                        "size-2 shrink-0 rounded-full",
                        status === "approved"
                          ? "bg-[var(--sh-success)]"
                          : status === "review_required" || status === "stale"
                            ? "bg-[var(--sh-warning)]"
                            : status === "ready" || status === "queued" || status === "running"
                              ? "bg-[var(--sh-brand-500)]"
                              : "bg-[var(--sh-line-strong)]",
                      )}
                    />
                    {!collapsed ? (
                      <>
                        <span className="min-w-0 flex-1 truncate">{item.label}</span>
                        <span className="shrink-0 text-[11px] font-medium text-[var(--sh-ink-muted)]">
                          {isActive ? "当前" : statusLabel(status)}
                        </span>
                      </>
                    ) : null}
                  </>
                )}
              </NavLink>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
