import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  FileCheck2,
  PauseCircle,
  Presentation,
  Video,
} from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { saveMockDraft, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const branchDefinitions = [
  {
    title: "教案",
    detail: "完整教案正文",
    icon: FileCheck2,
    to: "lesson-plan",
    nodeKey: "lesson-plan",
    fallbackStatus: "review_required" as const,
  },
  {
    title: "PPT",
    detail: "等待批准教案",
    icon: Presentation,
    to: "ppt-outline",
    nodeKey: "ppt-outline",
    fallbackStatus: "not_ready" as const,
  },
  {
    title: "课堂导入视频",
    detail: "先选择课堂导入方案",
    icon: Video,
    to: "master-script",
    nodeKey: "master-script",
    fallbackStatus: "not_ready" as const,
  },
];

export function ProjectOverviewPage() {
  const { projectId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const projectLessons = getApprovedProjectLessons(runtime, projectId);
  const firstLesson = projectLessons[0];
  const budgetResumed = runtime.drafts[`project:${projectId}:budget`]?.value === true;
  const budgetPaused = searchParams.get("scenario") === "budget_paused";
  const showBudgetNotice = budgetPaused || budgetResumed;
  const automationPaused = runtime.drafts[`project:${projectId}:automation`]?.value === true;
  const projectTasks = runtime.tasks.filter((task) => task.project_id === projectId);

  if (!project) {
    return (
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <EmptyState
          action={
            <Link className={buttonVariants({ variant: "secondary" })} to="/app/projects">
              返回项目列表
            </Link>
          }
          description="请从项目列表打开一个仍然存在的项目。"
          icon={BookOpen}
          title="找不到这个项目"
        />
      </div>
    );
  }

  if (searchParams.get("scenario") === "project_empty") {
    return (
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <FocusPageHeader
          description="一个项目对应一个小知识点教材。上传后会先检查范围，再安排课时。"
          title="新的课件项目"
        />
        <div className="mt-7 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]">
          <EmptyState
            action={
              <Link className={buttonVariants({ size: "lg" })} to="/app/projects/new">
                上传教材
                <ArrowRight aria-hidden="true" />
              </Link>
            }
            description="项目还没有教材，因此暂时不能安排课时或制作教案。"
            icon={BookOpen}
            title="先上传当前知识点的教材"
          />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1440px] space-y-4 px-4 py-4 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          project.automation_mode === "automatic" ? (
            <Button
              onClick={() =>
                saveMockDraft(`project:${projectId}:automation`, !automationPaused, { projectId })
              }
              variant="secondary"
            >
              <PauseCircle aria-hidden="true" />
              {automationPaused ? "继续自动制作" : "暂停自动制作"}
            </Button>
          ) : undefined
        }
        description={`${project.grade ?? "年级待确认"} · ${project.textbook_edition ?? "教材版本待确认"} · ${project.knowledge_point}`}
        status={<StatusBadge status={project.status === "active" ? "running" : "draft"} />}
        title={project.title}
      />

      <section className={`grid gap-3 ${showBudgetNotice ? "lg:grid-cols-[1.15fr_0.85fr]" : ""}`}>
        <article className="flex flex-col gap-3 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-card)] lg:flex-row lg:items-center">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold text-[var(--sh-brand-600)]">现在继续</p>
            <h2 className="mt-1 text-xl font-bold text-[var(--sh-ink-strong)]">
              {firstLesson
                ? `确认教案：${firstLesson.title.replace(/^第\s*\d+\s*课时\s*·\s*/, "")}`
                : "先安排课时"}
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-[var(--sh-ink-muted)]">
              {firstLesson
                ? "重点查看课堂探究环节，再决定是否通过。"
                : "上传教材后，先确认教材范围和课时安排。"}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            {firstLesson ? (
              <Link
                className={buttonVariants({ size: "md" })}
                to={`/app/projects/${projectId}/lessons/${firstLesson.id}/work/lesson-plan`}
              >
                打开教案
                <ArrowRight aria-hidden="true" />
              </Link>
            ) : null}
            <Link
              className={buttonVariants({ size: "md", variant: "secondary" })}
              to={`/app/projects/${projectId}/materials`}
            >
              查看教材与课时
            </Link>
          </div>
        </article>

        {showBudgetNotice ? (
          <aside
            className={`rounded-[var(--sh-radius-md)] border p-6 ${budgetResumed ? "border-[var(--sh-success)]/30 bg-[var(--sh-success-soft)]" : "border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)]"}`}
          >
            <div className="flex items-start gap-3">
              <AlertTriangle
                aria-hidden="true"
                className="mt-0.5 size-5 shrink-0 text-[var(--sh-warning)]"
              />
              <div>
                <h2 className="font-semibold text-[var(--sh-ink-strong)]">
                  {budgetResumed ? "已恢复这一批任务" : "全自动制作已在费用门槛暂停"}
                </h2>
                <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
                  {budgetResumed
                    ? "9 张 PPT 图片已开始重新制作，其他任务保持原状态。"
                    : "继续制作 9 张 PPT 图片预计需要 4.20 元。确认后仅恢复这一批任务。"}
                </p>
                {!budgetResumed ? (
                  <Button
                    className="mt-4"
                    onClick={() =>
                      saveMockDraft(`project:${projectId}:budget`, true, { projectId })
                    }
                    size="sm"
                  >
                    确认并继续
                  </Button>
                ) : null}
              </div>
            </div>
          </aside>
        ) : null}
      </section>

      <section aria-labelledby="lessons-title">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]" id="lessons-title">
            课时
          </h2>
          <Link
            className="text-sm font-semibold text-[var(--sh-brand-600)]"
            to={`/app/projects/${projectId}/lessons`}
          >
            查看课时工作台
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {projectLessons.map((lesson) => (
            <article
              className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5"
              key={lesson.id}
            >
              <div className="flex items-start gap-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                  <BookOpen aria-hidden="true" className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-[var(--sh-ink-strong)]">{lesson.title}</h3>
                  <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">{lesson.scope}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <StatusBadge status={lesson.planStatus} />
                    <span className="text-xs text-[var(--sh-ink-muted)]">
                      {lesson.duration} 分钟
                    </span>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="branches-title">
        <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]" id="branches-title">
          制作分支
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {branchDefinitions.map(({ detail, fallbackStatus, icon: Icon, nodeKey, title, to }) => {
            const status = firstLesson
              ? (runtime.nodeStates[`${projectId}:${firstLesson.id}:${nodeKey}`]?.status ??
                fallbackStatus)
              : "not_ready";
            const ready = status !== "not_ready";
            const targetStep = ready
              ? to
              : nodeKey === "ppt-outline"
                ? "lesson-plan"
                : nodeKey === "master-script"
                  ? "intro-options"
                  : to;
            const actionLabel = ready
              ? "打开"
              : nodeKey === "ppt-outline"
                ? "先确认教案"
                : nodeKey === "master-script"
                  ? "先选择导入方案"
                  : "查看准备条件";
            return (
              <Link
                className={`group rounded-[var(--sh-radius-md)] border p-5 ${ready ? "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] hover:border-[var(--sh-brand-300)]" : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-warm)]"}`}
                key={title}
                to={
                  firstLesson
                    ? `/app/projects/${projectId}/lessons/${firstLesson.id}/work/${targetStep}`
                    : `/app/projects/${projectId}/materials`
                }
              >
                <div className="flex items-center justify-between gap-3">
                  <Icon aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
                  <StatusBadge status={status} />
                </div>
                <h3 className="mt-5 font-semibold text-[var(--sh-ink-strong)]">{title}</h3>
                <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">{detail}</p>
                <span className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[var(--sh-brand-600)]">
                  {actionLabel}
                  <ArrowRight
                    aria-hidden="true"
                    className="size-4 transition-transform group-hover:translate-x-0.5"
                  />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      <section aria-labelledby="tasks-title">
        <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]" id="tasks-title">
          项目任务
        </h2>
        <div className="mt-4 divide-y divide-[var(--sh-line-subtle)] rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-5">
          {projectTasks.length ? (
            projectTasks.slice(0, 2).map((task) => (
              <div className="flex flex-wrap items-center gap-4 py-4" key={task.id}>
                <StatusBadge status={task.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">{task.title}</p>
                  <p className="text-xs text-[var(--sh-ink-muted)]">{task.detail}</p>
                </div>
                <span className="text-xs text-[var(--sh-ink-faint)]">
                  {new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(
                    new Date(task.updated_at),
                  )}
                </span>
              </div>
            ))
          ) : (
            <p className="py-6 text-sm text-[var(--sh-ink-muted)]">当前没有排队中的任务。</p>
          )}
        </div>
      </section>
    </div>
  );
}
