import { ArrowRight, BookOpen, Clock3, Image, PlaySquare, Presentation } from "lucide-react";
import { Link } from "react-router-dom";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { apiConfig } from "@/shared/api/config";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { useMockSession } from "@/shared/auth/mockAuth";
import { buttonVariants } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { HomeBrandHero } from "@/pages/home/HomeBrandHero";

const creativeEntries = [
  {
    detail: "画清楚课堂情境、教具和数学关系",
    icon: Image,
    label: "教学图片",
    title: "画清楚一个课堂情境",
    to: "/app/creation/images",
    type: "image" as const,
    variant: 0,
  },
  {
    detail: "把课堂问题变成有悬念的导入片段",
    icon: PlaySquare,
    label: "课堂视频",
    title: "把一个问题变成故事",
    to: "/app/creation/videos",
    type: "video" as const,
    variant: 1,
  },
  {
    detail: "从封面、知识页到练习完整制作",
    icon: Presentation,
    label: "教学 PPT",
    title: "完成一套课堂课件",
    to: "/app/creation/presentations",
    type: "presentation" as const,
    variant: 0,
  },
];

export function HomePage() {
  const session = useMockSession();
  const runtime = useMockRuntime();
  const projectQuery = useProjectsQuery();
  const currentProject = projectQuery.data?.[0];
  const currentLessonId = currentProject
    ? getApprovedProjectLessons(runtime, currentProject.id)[0]?.id
    : undefined;
  const continueTo = currentProject
    ? apiConfig.mode === "mock" && currentLessonId
      ? `/app/projects/${currentProject.id}/lessons/${currentLessonId}/work/lesson-plan`
      : `/app/projects/${currentProject.id}`
    : "/app/projects";
  const projectStateLabel = currentProject?.archived
    ? "已归档"
    : currentProject?.status === "draft"
      ? "准备课程"
      : "制作中";
  const projectProgress = currentProject?.archived
    ? 100
    : currentProject?.status === "draft"
      ? 18
      : 62;

  return (
    <div className="min-h-[calc(100vh-var(--sh-topbar-height))] bg-[var(--sh-surface-canvas)] px-4 py-4 md:px-5 md:py-5">
      <div className="mx-auto max-w-[1360px]">
        <HomeBrandHero
          continueTo={continueTo}
          hasProject={Boolean(currentProject)}
          role={session?.user.role}
        />

        <section aria-labelledby="continue-title" className="mt-5">
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="text-lg font-semibold" id="continue-title">
              继续完成这节课
            </h2>
            <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/projects">
              全部项目
            </Link>
          </div>
          {projectQuery.isLoading ? (
            <div
              className="h-36 animate-pulse rounded-[var(--sh-radius-lg)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
              role="status"
            >
              <span className="sr-only">正在读取最近项目</span>
            </div>
          ) : currentProject ? (
            <article className="grid overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] md:grid-cols-[230px_minmax(0,1fr)_auto] md:items-center">
              <div className="grid min-h-32 place-items-center bg-[var(--sh-brand-50)] p-3 md:h-full">
                {apiConfig.mode === "mock" ? (
                  <CreativeResultVisual type="presentation" variant={1} />
                ) : (
                  <span className="grid size-14 place-items-center rounded-full bg-[var(--sh-surface-elevated)] text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)]">
                    <BookOpen aria-hidden="true" className="size-6" />
                  </span>
                )}
              </div>
              <div className="min-w-0 p-4 md:px-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-[var(--sh-ink-muted)]">
                    {currentProject.grade} · {currentProject.textbookEdition}
                  </span>
                  <span className="rounded-full bg-[var(--sh-brand-50)] px-2.5 py-1 text-xs font-semibold text-[var(--sh-brand-700)]">
                    {projectStateLabel}
                  </span>
                </div>
                <h3 className="mt-2 truncate text-xl font-semibold">{currentProject.title}</h3>
                <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                  下一步：{currentProject.nextAction}
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <div
                    aria-label={`项目完成进度 ${String(projectProgress)}%`}
                    aria-valuemax={100}
                    aria-valuemin={0}
                    aria-valuenow={projectProgress}
                    className="h-1.5 w-full max-w-80 overflow-hidden rounded-full bg-[var(--sh-surface-soft)]"
                    role="progressbar"
                  >
                    <div
                      className="h-full rounded-full bg-[var(--sh-brand-500)]"
                      style={{ width: `${String(projectProgress)}%` }}
                    />
                  </div>
                  <span className="text-xs font-semibold text-[var(--sh-brand-700)]">
                    {projectProgress}%
                  </span>
                </div>
              </div>
              <div className="px-4 pb-4 md:pr-6 md:pb-0 md:pl-2">
                <Link
                  className={buttonVariants({ className: "w-full shrink-0 md:w-auto" })}
                  to={continueTo}
                >
                  继续制作
                  <ArrowRight aria-hidden="true" />
                </Link>
              </div>
            </article>
          ) : (
            <div className="rounded-[var(--sh-radius-lg)] bg-[var(--sh-surface-elevated)] p-6 text-center shadow-[var(--sh-shadow-card)]">
              <p className="text-sm text-[var(--sh-ink-muted)]">还没有项目，从一份教材开始。</p>
            </div>
          )}
        </section>

        <section aria-labelledby="creative-title" className="mt-5">
          <div className="mb-3 flex items-center justify-between gap-3 px-1">
            <h2 className="text-lg font-semibold" id="creative-title">
              也可以直接创作一件作品
            </h2>
            <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/creation">
              进入创作中心
            </Link>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {creativeEntries.map(({ detail, icon: Icon, label, title, to, type, variant }) => (
              <Link
                className="group grid min-h-40 grid-cols-[132px_minmax(0,1fr)] overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] transition-[transform,box-shadow] duration-[var(--sh-duration-normal)] hover:-translate-y-0.5 hover:shadow-[var(--sh-shadow-hover)] sm:grid-cols-[42%_minmax(0,1fr)] md:grid-cols-1 md:grid-rows-[132px_auto] xl:grid-cols-[42%_minmax(0,1fr)] xl:grid-rows-none"
                key={to}
                to={to}
              >
                <div className="h-full min-h-40 overflow-hidden bg-[var(--sh-surface-soft)] p-2 md:h-[132px] md:min-h-0 xl:h-auto [&>div]:h-full [&>div]:min-h-28 [&>div]:aspect-auto">
                  <CreativeResultVisual
                    ratio={type === "image" ? "4:3" : undefined}
                    type={type}
                    variant={variant}
                  />
                </div>
                <div className="flex min-w-0 flex-col justify-center p-4">
                  <span className="flex items-center gap-2 text-xs font-semibold text-[var(--sh-brand-600)]">
                    <Icon aria-hidden="true" className="size-4" />
                    {label}
                  </span>
                  <strong className="mt-2 text-base leading-5 text-[var(--sh-ink-strong)]">
                    {title}
                  </strong>
                  <span className="mt-1.5 line-clamp-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
                    {detail}
                  </span>
                  <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-[var(--sh-brand-700)]">
                    开始创作
                    <ArrowRight
                      aria-hidden="true"
                      className="size-3.5 transition-transform group-hover:translate-x-0.5"
                    />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {apiConfig.mode === "mock" ? (
          <section
            aria-label="最近项目和作品"
            className="mt-5 grid gap-4 border-t border-[var(--sh-line-subtle)] pt-5 lg:grid-cols-[minmax(0,1fr)_360px]"
          >
            <div>
              <div className="mb-3 flex items-center justify-between px-1">
                <h2 className="text-lg font-semibold">等待你处理</h2>
                <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/tasks">
                  全部任务
                </Link>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {runtime.tasks.slice(0, 2).map((task) => (
                  <Link
                    className="flex min-w-0 items-center gap-3 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] px-3 py-3 shadow-[var(--sh-shadow-card)] hover:bg-[var(--sh-surface-soft)]"
                    key={task.id}
                    to="/app/tasks"
                  >
                    <StatusBadge status={task.status} />
                    <span className="min-w-0 flex-1 truncate text-sm font-medium">
                      {task.title}
                    </span>
                    <ArrowRight
                      aria-hidden="true"
                      className="size-4 shrink-0 text-[var(--sh-brand-600)]"
                    />
                  </Link>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-3 flex items-center justify-between px-1">
                <h2 className="text-lg font-semibold">最近作品</h2>
              </div>
              <div className="grid gap-2">
                <Link
                  className="flex items-center gap-3 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-2 shadow-[var(--sh-shadow-card)] hover:bg-[var(--sh-surface-soft)]"
                  to="/app/creation/images"
                >
                  <div className="w-20 shrink-0 overflow-hidden rounded-[var(--sh-radius-sm)] [&>div]:aspect-video">
                    <CreativeResultVisual type="image" variant={0} />
                  </div>
                  <span className="min-w-0">
                    <strong className="block truncate text-sm">果汁标签观察图</strong>
                    <span className="mt-1 flex items-center gap-1 text-xs text-[var(--sh-ink-muted)]">
                      <Clock3 aria-hidden="true" className="size-3.5" />
                      12 分钟前
                    </span>
                  </span>
                </Link>
              </div>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
