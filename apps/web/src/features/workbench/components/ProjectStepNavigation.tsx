import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { NavLink, useLocation, useParams } from "react-router-dom";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { getWorkbenchStepStatus } from "@/features/workbench/lib/stepAccess";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { projectSteps } from "@/shared/data/mockData";
import { cn } from "@/shared/lib/cn";

type ProjectStepNavigationProps = {
  activeStepKey?: string;
  base: string;
  collapsed?: boolean;
  lessonId?: string;
  onNavigate?: () => void;
  projectId?: string;
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
  activeStepKey,
  base,
  collapsed = false,
  lessonId: lessonIdProp,
  onNavigate,
  projectId: projectIdProp,
}: ProjectStepNavigationProps) {
  const { lessonId: routeLessonId = "", projectId: routeProjectId = "" } = useParams();
  const lessonId = lessonIdProp ?? routeLessonId;
  const projectId = projectIdProp ?? routeProjectId;
  const location = useLocation();
  const navigationRef = useRef<HTMLElement>(null);
  const activeStepRef = useRef<HTMLAnchorElement>(null);
  const [indicatorPosition, setIndicatorPosition] = useState<{
    height: number;
    top: number;
  } | null>(null);
  const runtime = useMockRuntime();
  const currentPath = location.pathname.replace(/\/$/, "");

  useLayoutEffect(() => {
    const activeStep = activeStepRef.current;
    const navigation = navigationRef.current;
    if (!activeStep || !navigation) return;
    const activeRect = activeStep.getBoundingClientRect();
    const navigationRect = navigation.getBoundingClientRect();
    setIndicatorPosition({
      height: activeRect.height,
      top: activeRect.top - navigationRect.top,
    });
  }, [activeStepKey, collapsed, currentPath]);

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
  }, [activeStepKey, currentPath]);

  return (
    <nav
      aria-label="课时制作流程"
      className="relative px-2 pb-[calc((100dvh-var(--sh-topbar-height)-52px)/2)]"
      ref={navigationRef}
    >
      {indicatorPosition ? (
        <span
          aria-hidden="true"
          className="pointer-events-none absolute left-2 right-2 top-0 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] transition-[transform,height] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none"
          data-testid="project-step-active-indicator"
          style={{
            height: indicatorPosition.height,
            transform: `translateY(${String(indicatorPosition.top)}px)`,
          }}
        >
          <span className="absolute bottom-2 left-0 top-2 w-[3px] rounded-r-full bg-[var(--sh-brand-500)]" />
        </span>
      ) : null}
      {projectSteps.map((group) => (
        <div className="relative z-10 mb-5" key={group.group}>
          {!collapsed ? (
            <p className="mb-1 px-3 text-xs font-semibold text-[var(--sh-ink-muted)]">
              {group.group}
            </p>
          ) : null}
          {group.items.map((item) => {
            const status = getWorkbenchStepStatus(runtime, projectId, lessonId, item.key);
            const stepPath = `${base}/${item.key}`;
            const externallyActive = activeStepKey === item.key;
            return (
              <NavLink
                className={({ isActive }) => {
                  const active = externallyActive || isActive;
                  return cn(
                    "relative mb-0.5 flex min-h-11 items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 text-sm text-[var(--sh-ink-muted)] transition-colors duration-[var(--sh-duration-normal)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]",
                    active && "font-semibold text-[var(--sh-brand-700)]",
                    collapsed && "justify-center px-2",
                  );
                }}
                data-current={externallyActive ? "true" : undefined}
                key={item.key}
                onClick={onNavigate}
                ref={externallyActive || currentPath === stepPath ? activeStepRef : undefined}
                title={collapsed ? item.label : undefined}
                to={stepPath}
              >
                {({ isActive }) => (
                  <>
                    <span
                      aria-hidden="true"
                      className={cn(
                        "relative z-10 size-2 shrink-0 rounded-full",
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
                        <span className="relative z-10 min-w-0 flex-1 truncate">{item.label}</span>
                        <span className="relative z-10 shrink-0 text-[11px] font-medium text-[var(--sh-ink-muted)]">
                          {externallyActive || isActive ? "当前" : statusLabel(status)}
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
