import * as Dialog from "@radix-ui/react-dialog";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  Check,
  ArrowLeft,
  ChevronLeft,
  CirclePause,
  Menu,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Play,
  X,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link, Outlet, useParams } from "react-router-dom";
import { ContextDrawer } from "@/features/workbench/components/ContextDrawer";
import { ProjectStepNavigation } from "@/features/workbench/components/ProjectStepNavigation";
import { TaskStatusBar } from "@/features/workbench/components/TaskStatusBar";
import { getPreviousWorkbenchStepKey } from "@/features/workbench/lib/stepAccess";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import { saveMockDraft, updateMockProject, useMockRuntime } from "@/shared/api/mockClient";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { projectSteps } from "@/shared/data/mockData";
import { cn } from "@/shared/lib/cn";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

const automationOptions = [
  { label: "逐步确认", value: "assisted" },
  { label: "自动完成", value: "automatic" },
] as const;

export function ProjectWorkbenchLayout() {
  const { lessonId = "", projectId = "", stepKey = "" } = useParams();
  const { sidebarCollapsed, toggleSidebar } = useWorkbenchUi();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileFlowTriggerRef = useRef<HTMLButtonElement>(null);
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const lesson = getApprovedProjectLessons(runtime, projectId).find((item) => item.id === lessonId);
  const paused = runtime.drafts[`project:${projectId}:paused`]?.value === true;
  const currentStepLabel =
    projectSteps.flatMap((group) => group.items).find((item) => item.key === stepKey)?.label ??
    "当前步骤";
  const automationMode = project?.automation_mode ?? "assisted";
  const publicAutomationMode = automationMode === "automatic" ? "automatic" : "assisted";
  const base = `/app/projects/${projectId}/lessons/${lessonId}/work`;
  const workflowSteps = projectSteps.flatMap((group) => group.items);
  const previousStepKey = getPreviousWorkbenchStepKey(stepKey);
  const previousStep = workflowSteps.find((item) => item.key === previousStepKey);
  useProjectEvents(projectId);

  return (
    <div
      className="relative flex h-[calc(100dvh-var(--sh-topbar-height))] flex-col overflow-hidden bg-[var(--sh-surface-canvas)]"
      data-testid="project-workbench"
    >
      <header className="z-30 flex min-h-[52px] shrink-0 items-center gap-2 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/96 px-3 shadow-[var(--sh-shadow-card)] backdrop-blur-sm md:gap-3 md:px-5">
        <Link
          aria-label="返回项目"
          className="inline-grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
          to={`/app/projects/${projectId}`}
        >
          <ChevronLeft aria-hidden="true" className="size-5" />
        </Link>
        <div
          aria-label={`当前上下文：${project?.title ?? "项目"}，${lesson?.title ?? "当前课时"}，${currentStepLabel}`}
          className="flex min-w-0 flex-1 flex-col justify-center gap-0.5 leading-tight"
        >
          <span className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
            {project?.title ?? "项目"}
          </span>
          <span className="truncate text-[11px] text-[var(--sh-ink-muted)] sm:text-xs">
            {lesson?.title ?? "当前课时"} · {currentStepLabel}
          </span>
        </div>

        {previousStep ? (
          <Button
            aria-label={`上一步：${previousStep.label}`}
            asChild
            className="size-9 px-0 sm:size-auto sm:px-3"
            size="sm"
            variant="quiet"
          >
            <Link to={`${base}/${previousStep.key}`}>
              <ArrowLeft aria-hidden="true" />
              <span className="hidden sm:inline">上一步</span>
            </Link>
          </Button>
        ) : null}

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <IconButton label="更多工作台操作">
              <MoreHorizontal aria-hidden="true" />
            </IconButton>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              className="z-50 min-w-52 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-1.5 shadow-[var(--sh-shadow-floating)]"
              sideOffset={8}
            >
              <DropdownMenu.Label className="px-3 py-1.5 text-xs text-[var(--sh-ink-muted)]">
                推进方式
              </DropdownMenu.Label>
              <DropdownMenu.RadioGroup
                onValueChange={(value) =>
                  updateMockProject(projectId, {
                    automation_mode: value as "manual" | "assisted" | "automatic",
                  })
                }
                value={publicAutomationMode}
              >
                {automationOptions.map((option) => (
                  <DropdownMenu.RadioItem
                    className="relative flex cursor-pointer items-center rounded-[var(--sh-radius-sm)] py-2 pl-8 pr-3 text-sm outline-none hover:bg-[var(--sh-surface-soft)]"
                    key={option.value}
                    value={option.value}
                  >
                    <DropdownMenu.ItemIndicator className="absolute left-2">
                      <Check aria-hidden="true" className="size-4 text-[var(--sh-brand-700)]" />
                    </DropdownMenu.ItemIndicator>
                    {option.label}
                  </DropdownMenu.RadioItem>
                ))}
              </DropdownMenu.RadioGroup>
              <DropdownMenu.Separator className="my-1 h-px bg-[var(--sh-line-subtle)]" />
              <DropdownMenu.Item
                className="flex cursor-pointer items-center gap-2 rounded-[var(--sh-radius-sm)] px-3 py-2 text-sm outline-none hover:bg-[var(--sh-surface-soft)]"
                onSelect={() =>
                  saveMockDraft(`project:${projectId}:paused`, !paused, { projectId })
                }
              >
                {paused ? (
                  <Play aria-hidden="true" className="size-4" />
                ) : (
                  <CirclePause aria-hidden="true" className="size-4" />
                )}
                {paused ? "继续制作" : "暂停制作"}
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <Button
          aria-label="打开课时流程"
          className="shrink-0 md:hidden"
          onClick={() => setMobileOpen(true)}
          ref={mobileFlowTriggerRef}
          size="sm"
          variant="secondary"
        >
          <Menu aria-hidden="true" />
          流程
        </Button>
      </header>

      <div className="flex min-h-0 flex-1 items-stretch overflow-hidden">
        <aside
          className={cn(
            "hidden h-full shrink-0 overflow-y-auto border-r border-[var(--sh-line-default)] bg-[var(--sh-brand-50)] transition-[width] duration-[var(--sh-duration-normal)] md:block",
            sidebarCollapsed ? "w-16" : "w-[var(--sh-project-sidebar-width)]",
          )}
          data-step-scroll-container
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

        <section
          className="h-full min-w-0 flex-1 overflow-y-auto outline-none"
          data-testid="workbench-content"
        >
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
            data-step-scroll-container
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
