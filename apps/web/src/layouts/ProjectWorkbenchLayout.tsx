import * as Dialog from "@radix-ui/react-dialog";
import {
  ChevronLeft,
  ChevronRight,
  CirclePause,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  X,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { saveMockDraft, updateMockProject, useMockRuntime } from "@/shared/api/mocks/runtime";
import { cn } from "@/shared/lib/cn";
import { IconButton } from "@/shared/ui/IconButton";
import { Select } from "@/shared/ui/Select";
import { ContextDrawer } from "@/features/workbench/components/ContextDrawer";
import { ProjectStepNavigation } from "@/features/workbench/components/ProjectStepNavigation";
import { TaskStatusBar } from "@/features/workbench/components/TaskStatusBar";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { useProjectEvents } from "@/shared/api/useProjectEvents";

export function ProjectWorkbenchLayout() {
  const { lessonId = "", projectId = "" } = useParams();
  const { sidebarCollapsed, toggleSidebar } = useWorkbenchUi();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileFlowTriggerRef = useRef<HTMLButtonElement>(null);
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const lesson = getApprovedProjectLessons(runtime, projectId).find((item) => item.id === lessonId);
  const paused = runtime.drafts[`project:${projectId}:paused`]?.value === true;
  const base = `/app/projects/${projectId}/lessons/${lessonId}/work`;
  useProjectEvents(projectId);

  return (
    <div
      className="relative flex min-h-[calc(100dvh-var(--sh-topbar-height))] flex-col bg-[var(--sh-surface-canvas)]"
      data-testid="project-workbench"
    >
      <header className="sticky top-[var(--sh-topbar-height)] z-30 flex min-h-[52px] items-center gap-3 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/96 px-3 shadow-[var(--sh-shadow-card)] backdrop-blur-sm md:px-5">
        <Link
          aria-label="返回项目"
          className="inline-grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
          to={`/app/projects/${projectId}`}
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <div className="hidden min-w-0 items-center gap-2 md:flex">
          <span className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
            {project?.title ?? "项目"}
          </span>
          <ChevronRight aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
          <span className="truncate text-sm text-[var(--sh-ink-muted)]">
            {lesson?.title ?? "当前课时"}
          </span>
        </div>
        <Select
          ariaLabel="推进方式"
          className="ml-auto hidden w-28 sm:inline-flex"
          onValueChange={(automationMode) =>
            updateMockProject(projectId, {
              automation_mode: automationMode as "manual" | "assisted" | "automatic",
            })
          }
          options={[
            { label: "每步确认", value: "manual" },
            { label: "系统先准备", value: "assisted" },
            { label: "自动推进", value: "automatic" },
          ]}
          size="sm"
          value={project?.automation_mode ?? "assisted"}
        />
        <IconButton
          className="text-[var(--sh-warning)]"
          label={paused ? "继续制作" : "暂停制作"}
          onClick={() => saveMockDraft(`project:${projectId}:paused`, !paused, { projectId })}
        >
          <CirclePause aria-hidden="true" />
        </IconButton>
        <IconButton
          className="md:hidden"
          label="打开课时流程"
          onClick={() => setMobileOpen(true)}
          ref={mobileFlowTriggerRef}
        >
          <Menu aria-hidden="true" />
        </IconButton>
      </header>

      <div className="flex flex-1 items-start">
        <aside
          className={cn(
            "hidden shrink-0 border-r border-[var(--sh-line-default)] bg-[var(--sh-brand-50)] transition-[width] duration-[var(--sh-duration-normal)] md:sticky md:top-[calc(var(--sh-topbar-height)+52px)] md:block md:max-h-[calc(100dvh-var(--sh-topbar-height)-52px)] md:overflow-y-auto",
            sidebarCollapsed ? "w-16" : "w-[var(--sh-project-sidebar-width)]",
          )}
        >
          <div className="flex h-12 items-center justify-end px-3">
            <IconButton label={sidebarCollapsed ? "展开流程" : "收起流程"} onClick={toggleSidebar}>
              {sidebarCollapsed ? (
                <PanelLeftOpen aria-hidden="true" />
              ) : (
                <PanelLeftClose aria-hidden="true" />
              )}
            </IconButton>
          </div>
          <ProjectStepNavigation base={base} collapsed={sidebarCollapsed} />
        </aside>

        <section className="min-w-0 flex-1" data-testid="workbench-content">
          <Outlet />
        </section>
      </div>
      <TaskStatusBar projectId={projectId} />
      <ContextDrawer />
      <Dialog.Root onOpenChange={setMobileOpen} open={mobileOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)]" />
          <Dialog.Content
            className="fixed inset-y-0 left-0 z-50 w-[min(86vw,320px)] overflow-y-auto bg-[var(--sh-surface-elevated)] p-3 shadow-[var(--sh-shadow-modal)] md:hidden"
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              mobileFlowTriggerRef.current?.focus();
            }}
            onEscapeKeyDown={() => setMobileOpen(false)}
          >
            <div className="mb-3 flex min-h-12 items-center justify-between px-2">
              <Dialog.Title className="font-semibold text-[var(--sh-ink-strong)]">
                课时制作流程
              </Dialog.Title>
              <Dialog.Description className="sr-only">选择要打开的课时制作步骤</Dialog.Description>
              <Dialog.Close asChild>
                <IconButton label="关闭课时流程">
                  <X aria-hidden="true" />
                </IconButton>
              </Dialog.Close>
            </div>
            <ProjectStepNavigation base={base} onNavigate={() => setMobileOpen(false)} />
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
