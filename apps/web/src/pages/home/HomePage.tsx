import { ArrowRight, BookOpen, Image, PlaySquare, Presentation } from "lucide-react";
import { Link } from "react-router-dom";
import emptyProjectDesk from "@/assets/illustrations/empty-project-desk.webp";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { buttonVariants } from "@/shared/ui/Button";
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
    available: true,
  },
  {
    detail: "把课堂问题变成有悬念的导入片段",
    icon: PlaySquare,
    label: "课堂视频",
    title: "把一个问题变成故事",
    to: "/app/creation/videos",
    type: "video" as const,
    variant: 1,
    available: true,
  },
  {
    detail: "从封面、知识页到练习完整制作",
    icon: Presentation,
    label: "教学 PPT",
    title: "完成一套课堂课件",
    to: "/app/creation/presentations",
    type: "presentation" as const,
    variant: 0,
    available: false,
  },
];

function CreativeEntryCard({
  detail,
  icon: Icon,
  label,
  title,
  to,
  type,
  variant,
  available,
}: (typeof creativeEntries)[number]) {
  const content = (
    <>
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
        <strong className="mt-2 text-base leading-5 text-[var(--sh-ink-strong)]">{title}</strong>
        <span className="mt-1.5 line-clamp-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
          {detail}
        </span>
        <span
          className={`mt-3 inline-flex items-center gap-1 text-xs font-semibold ${available ? "text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-muted)]"}`}
        >
          {available ? "开始创作" : "后续开放"}
          {available ? <ArrowRight aria-hidden="true" className="size-3.5" /> : null}
        </span>
      </div>
    </>
  );

  const className =
    "group grid min-h-40 grid-cols-[132px_minmax(0,1fr)] overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] sm:grid-cols-[42%_minmax(0,1fr)] md:grid-cols-1 md:grid-rows-[132px_auto] xl:grid-cols-[42%_minmax(0,1fr)] xl:grid-rows-none";

  return available ? (
    <Link
      className={`${className} transition-[transform,box-shadow] duration-[var(--sh-duration-normal)] hover:-translate-y-0.5 hover:shadow-[var(--sh-shadow-hover)]`}
      key={to}
      to={to}
    >
      {content}
    </Link>
  ) : (
    <article aria-disabled="true" className={`${className} opacity-80`} key={to}>
      {content}
    </article>
  );
}

export function HomePage({ creationAvailable = true }: { creationAvailable?: boolean }) {
  const projectQuery = useProjectsQuery();
  const currentProject = projectQuery.data?.[0];
  const continueTo = currentProject ? `/app/projects/${currentProject.id}` : "/app/projects";

  return (
    <div className="min-h-[calc(100vh-var(--sh-topbar-height))] bg-[var(--sh-surface-canvas)] px-4 py-4 md:px-5 md:py-5">
      <div className="mx-auto max-w-[1360px]">
        <HomeBrandHero continueTo={continueTo} hasProject={Boolean(currentProject)} />

        <section aria-labelledby="continue-title" className="mt-5">
          <div className="mb-3 flex items-center justify-between px-1">
            <h2 className="text-lg font-semibold" id="continue-title">
              {currentProject ? "继续完成这节课" : "从第一份教材开始"}
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
          ) : projectQuery.isError ? (
            <div className="rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 text-center shadow-[var(--sh-shadow-card)]">
              <p className="text-sm text-[var(--sh-ink-muted)]">项目暂时无法读取，请稍后再试。</p>
            </div>
          ) : currentProject ? (
            <article className="grid overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] md:grid-cols-[230px_minmax(0,1fr)_auto] md:items-center">
              <div className="grid min-h-32 place-items-center bg-[var(--sh-brand-50)] p-3 md:h-full">
                <span className="grid size-14 place-items-center rounded-full bg-[var(--sh-surface-elevated)] text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)]">
                  <BookOpen aria-hidden="true" className="size-6" />
                </span>
              </div>
              <div className="min-w-0 p-4 md:px-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-[var(--sh-ink-muted)]">
                    {currentProject.grade} · {currentProject.textbookEdition}
                  </span>
                  <span className="rounded-full bg-[var(--sh-brand-50)] px-2.5 py-1 text-xs font-semibold text-[var(--sh-brand-700)]">
                    {currentProject.progressLabel}
                  </span>
                </div>
                <h3 className="mt-2 truncate text-xl font-semibold">{currentProject.title}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-[var(--sh-ink-muted)]">
                  {currentProject.nextAction ?? currentProject.knowledgePoint}
                </p>
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
            <div className="grid grid-cols-[112px_minmax(0,1fr)] overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)] sm:grid-cols-[160px_minmax(0,1fr)_auto] sm:items-center lg:grid-cols-[200px_minmax(0,1fr)_auto]">
              <img
                alt="等待开始备课的温暖书桌"
                className="h-full min-h-32 w-full object-cover"
                decoding="async"
                src={emptyProjectDesk}
              />
              <div className="min-w-0 p-4 sm:px-5">
                <p className="font-semibold text-[var(--sh-ink-strong)]">还没有项目</p>
                <p className="mt-1 text-sm leading-5 text-[var(--sh-ink-muted)]">
                  上传一份教材，开始整理你的第一节课。
                </p>
              </div>
              <Link
                className={buttonVariants({
                  className: "col-span-2 mx-4 mb-4 shrink-0 sm:col-span-1 sm:mx-4 sm:mb-0 lg:mx-5",
                })}
                to="/app/projects/new"
              >
                创建第一个项目
                <ArrowRight aria-hidden="true" />
              </Link>
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
            {creativeEntries.map((entry) => (
              <CreativeEntryCard
                {...entry}
                available={entry.type === "presentation" ? false : creationAvailable}
                key={entry.to}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
