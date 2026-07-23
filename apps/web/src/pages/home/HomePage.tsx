import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  CircleX,
  Image,
  Info,
  LoaderCircle,
  PlaySquare,
  Presentation,
} from "lucide-react";
import { Link } from "react-router-dom";
import emptyProjectDesk from "@/assets/illustrations/empty-project-desk.webp";
import type { ProjectSummary } from "@/entities/project/model";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import type { StudioType } from "@/features/creation-studio/model";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { HomeBrandHero } from "@/pages/home/HomeBrandHero";
import { buttonVariants } from "@/shared/ui/Button";

const creativeEntries = [
  {
    available: true,
    detail: "画清楚课堂情境、教具和数学关系",
    icon: Image,
    label: "教学图片",
    title: "画清楚一个课堂情境",
    to: "/app/creation/images",
    type: "image" as const,
    variant: 0,
  },
  {
    available: true,
    detail: "把课堂问题变成有悬念的导入片段",
    icon: PlaySquare,
    label: "课堂视频",
    title: "把一个问题变成故事",
    to: "/app/creation/videos",
    type: "video" as const,
    variant: 1,
  },
  {
    available: false,
    detail: "从封面、知识页到练习完整制作",
    icon: Presentation,
    label: "教学 PPT",
    title: "完成一套课堂课件",
    to: "/app/creation/presentations",
    type: "presentation" as const,
    variant: 0,
  },
];

export type HomeAttentionItem = {
  detail: string;
  label: string;
  status: "failed" | "review" | "running";
  to: string;
};

export type HomeRecentResult = {
  label: string;
  page?: number;
  ratio?: string;
  to: string;
  type: StudioType;
  variant: number;
};

function CreativeEntryCard({
  available,
  detail,
  icon: Icon,
  label,
  title,
  to,
  type,
  variant,
}: (typeof creativeEntries)[number]) {
  const content = (
    <>
      <div className="h-28 overflow-hidden bg-[var(--sh-surface-soft)] p-1.5 sm:h-32">
        <CreativeResultVisual
          loading="lazy"
          ratio={type === "image" ? "4:3" : undefined}
          type={type}
          variant={variant}
        />
      </div>
      <div className="flex min-w-0 flex-col justify-center p-3.5">
        <span className="flex items-center gap-2 text-xs font-semibold text-[var(--sh-brand-600)]">
          <Icon aria-hidden="true" className="size-4" />
          {label}
        </span>
        <strong className="mt-1.5 text-sm leading-5 text-[var(--sh-ink-strong)]">{title}</strong>
        <span className="mt-1 line-clamp-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
          {detail}
        </span>
        <span
          className={`mt-2 inline-flex items-center gap-1 text-xs font-semibold ${available ? "text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-muted)]"}`}
        >
          {available ? "开始创作" : "后续开放"}
          {available ? <ArrowRight aria-hidden="true" className="size-3.5" /> : null}
        </span>
      </div>
    </>
  );
  const className =
    "grid min-h-28 grid-cols-[112px_minmax(0,1fr)] overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] sm:grid-cols-[132px_minmax(0,1fr)]";

  return available ? (
    <Link
      className={`${className} transition-[border-color,box-shadow] duration-[var(--sh-duration-normal)] hover:border-[var(--sh-brand-300)] hover:shadow-[var(--sh-shadow-card)]`}
      to={to}
    >
      {content}
    </Link>
  ) : (
    <article aria-disabled="true" className={`${className} opacity-80`}>
      {content}
    </article>
  );
}

function RecentResults({ results }: { results: readonly HomeRecentResult[] }) {
  return (
    <section aria-labelledby="recent-results-title" className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3 px-1">
        <h2 className="text-base font-semibold" id="recent-results-title">
          最近成果
        </h2>
        {results.length > 0 ? (
          <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/creation">
            查看创作中心
          </Link>
        ) : null}
      </div>
      {results.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-3">
          {results.map((result) => (
            <Link
              className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-2 transition-[border-color,box-shadow] hover:border-[var(--sh-brand-300)] hover:shadow-[var(--sh-shadow-card)]"
              key={result.label}
              to={result.to}
            >
              <div className="aspect-[4/3] overflow-hidden rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)]">
                <CreativeResultVisual
                  loading="lazy"
                  page={result.page}
                  ratio={result.ratio}
                  type={result.type}
                  variant={result.variant}
                />
              </div>
              <p className="mt-2 truncate px-1 text-sm font-medium text-[var(--sh-ink-strong)]">
                {result.label}
              </p>
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 py-3 text-sm text-[var(--sh-ink-muted)]">
          完成并保存的作品会出现在这里。
        </div>
      )}
    </section>
  );
}

function AttentionSummary({
  fallbackTo,
  items,
}: {
  fallbackTo: string;
  items: readonly HomeAttentionItem[];
}) {
  if (items.length === 0) {
    return (
      <div className="mt-3 flex items-center gap-2 text-sm text-[var(--sh-ink-muted)]">
        <Info aria-hidden="true" className="size-4 shrink-0" />
        暂无可显示的待确认或失败任务
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-2">
      {items.slice(0, 3).map((item) => {
        const Icon =
          item.status === "failed"
            ? CircleX
            : item.status === "running"
              ? LoaderCircle
              : AlertCircle;
        const iconClass =
          item.status === "failed"
            ? "text-[var(--sh-danger)]"
            : item.status === "running"
              ? "text-[var(--sh-brand-600)]"
              : "text-[var(--sh-warning)]";
        return (
          <Link
            className="flex min-w-0 items-start gap-2.5 rounded-[var(--sh-radius-sm)] px-1 py-1 hover:bg-[var(--sh-surface-soft)]"
            key={`${item.label}:${item.to}`}
            to={item.to || fallbackTo}
          >
            <Icon aria-hidden="true" className={`mt-0.5 size-4 shrink-0 ${iconClass}`} />
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                {item.label}
              </span>
              <span className="mt-0.5 block line-clamp-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
                {item.detail}
              </span>
            </span>
          </Link>
        );
      })}
    </div>
  );
}

function hasWorkflowSummary(project: ProjectSummary) {
  return Boolean(project.currentLesson || project.nextAction);
}

function sortByRecentActivity(projects: ProjectSummary[]) {
  return projects
    .map((project, index) => ({ index, project }))
    .sort((left, right) => {
      const leftTime = left.project.updatedAtIso
        ? Date.parse(left.project.updatedAtIso)
        : Number.NaN;
      const rightTime = right.project.updatedAtIso
        ? Date.parse(right.project.updatedAtIso)
        : Number.NaN;
      if (!Number.isFinite(leftTime) || !Number.isFinite(rightTime))
        return left.index - right.index;
      return rightTime - leftTime;
    })
    .map(({ project }) => project);
}

function ProjectChoices({ projects }: { projects: ProjectSummary[] }) {
  return (
    <section aria-labelledby="project-choice-title" className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-3 px-1">
        <h2 className="text-base font-semibold" id="project-choice-title">
          选择项目继续
        </h2>
        <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/projects">
          全部项目
        </Link>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {projects.slice(0, 4).map((project) => (
          <Link
            className="flex min-w-0 items-center gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-3 py-2.5 hover:border-[var(--sh-brand-300)]"
            key={project.id}
            to={`/app/projects/${project.id}`}
          >
            <BookOpen aria-hidden="true" className="size-4 shrink-0 text-[var(--sh-brand-600)]" />
            <span className="min-w-0 flex-1 truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
              {project.title}
            </span>
            <span className="shrink-0 text-xs text-[var(--sh-ink-muted)]">{project.updatedAt}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function HomePage({
  attentionItems = [],
  creationAvailable = true,
  recentResults = [],
}: {
  attentionItems?: readonly HomeAttentionItem[];
  creationAvailable?: boolean;
  recentResults?: readonly HomeRecentResult[];
}) {
  const projectQuery = useProjectsQuery();
  const projects = sortByRecentActivity(projectQuery.data ?? []);
  const currentProject =
    projects.length === 1
      ? projects[0]
      : (projects.find(hasWorkflowSummary) ?? (creationAvailable ? projects[0] : undefined));
  const needsProjectChoice = projects.length > 1 && !currentProject;
  const continueTo = currentProject ? `/app/projects/${currentProject.id}` : "/app/projects";
  const attentionTarget = attentionItems[0]?.to;
  const nextAction = projectQuery.isLoading
    ? "正在读取项目"
    : projectQuery.isError
      ? "项目暂时无法读取"
      : (currentProject?.nextAction ??
        (currentProject
          ? "继续当前项目"
          : needsProjectChoice
            ? "选择一个项目继续"
            : "创建课程项目"));
  const nextDetail = currentProject?.currentLesson ?? currentProject?.knowledgePoint;
  const brandHeading = projectQuery.isLoading
    ? "正在读取课堂项目"
    : projectQuery.isError
      ? "项目暂时无法读取"
      : needsProjectChoice
        ? "选择今天要继续的项目"
        : undefined;

  return (
    <div className="min-h-[calc(100vh-var(--sh-topbar-height))] bg-[var(--sh-surface-canvas)] px-4 py-4 md:px-5 md:py-5 lg:py-4">
      <div className="mx-auto max-w-[1360px]">
        <HomeBrandHero
          hasProject={Boolean(currentProject)}
          heading={brandHeading}
          lessonTitle={currentProject?.currentLesson ?? currentProject?.knowledgePoint}
          projectTitle={currentProject?.title}
        />

        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1.3fr)_minmax(280px,0.7fr)]">
          <section
            aria-labelledby="next-action-title"
            className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4"
          >
            <p className="flex items-center gap-2 text-xs font-semibold text-[var(--sh-brand-600)]">
              <ArrowRight aria-hidden="true" className="size-4" />
              下一件事
            </p>
            <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div className="min-w-0">
                <h2 className="truncate text-lg font-semibold" id="next-action-title">
                  {nextAction}
                </h2>
                {nextDetail ? (
                  <p className="mt-1 truncate text-sm text-[var(--sh-ink-muted)]">{nextDetail}</p>
                ) : null}
              </div>
              {!projectQuery.isLoading && !projectQuery.isError ? (
                <Link
                  className={buttonVariants({ className: "shrink-0", size: "sm" })}
                  to={
                    currentProject
                      ? continueTo
                      : needsProjectChoice
                        ? "/app/projects"
                        : "/app/projects/new"
                  }
                >
                  {currentProject ? "打开项目" : needsProjectChoice ? "选择项目" : "创建第一个项目"}
                  <ArrowRight aria-hidden="true" />
                </Link>
              ) : null}
            </div>
          </section>

          <section
            aria-labelledby="attention-title"
            className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold" id="attention-title">
                待确认或失败
              </h2>
              {currentProject || needsProjectChoice ? (
                <Link
                  className="text-xs font-medium text-[var(--sh-brand-700)]"
                  to={attentionTarget ?? continueTo}
                >
                  {attentionTarget ? "查看任务" : currentProject ? "进入项目" : "查看项目"}
                </Link>
              ) : null}
            </div>
            <AttentionSummary fallbackTo={continueTo} items={attentionItems} />
          </section>
        </div>

        {currentProject ? (
          <section aria-labelledby="continue-title" className="mt-4">
            <div className="mb-2 flex items-center justify-between px-1">
              <h2 className="text-base font-semibold" id="continue-title">
                继续完成这节课
              </h2>
              <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/projects">
                全部项目
              </Link>
            </div>
            <article className="flex min-w-0 items-center gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-3 py-2.5">
              <span className="grid size-9 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
                <BookOpen aria-hidden="true" className="size-4" />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {currentProject.title}
                </h3>
                <p className="mt-0.5 truncate text-xs text-[var(--sh-ink-muted)]">
                  {currentProject.currentLesson ?? currentProject.knowledgePoint}
                </p>
              </div>
              <span className="hidden shrink-0 text-xs text-[var(--sh-ink-muted)] sm:inline">
                {currentProject.progressLabel}
              </span>
              <Link
                className={buttonVariants({ className: "shrink-0", size: "sm", variant: "quiet" })}
                to={continueTo}
              >
                继续制作
                <ArrowRight aria-hidden="true" />
              </Link>
            </article>
          </section>
        ) : needsProjectChoice ? (
          <ProjectChoices projects={projects} />
        ) : !projectQuery.isLoading && !projectQuery.isError ? (
          <div className="mt-4 flex items-center gap-3 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-3">
            <img
              alt="等待开始备课的温暖书桌"
              className="size-16 rounded-[var(--sh-radius-sm)] object-cover"
              decoding="async"
              src={emptyProjectDesk}
            />
            <p className="text-sm text-[var(--sh-ink-muted)]">
              创建项目后，这里会显示课程信息和已有课时。
            </p>
          </div>
        ) : null}

        <RecentResults results={recentResults} />

        {creationAvailable ? (
          <section aria-labelledby="creative-title" className="mt-5">
            <div className="mb-2 flex items-center justify-between gap-3 px-1">
              <h2 className="text-base font-semibold" id="creative-title">
                也可以直接创作一件作品
              </h2>
              <Link className="text-sm font-medium text-[var(--sh-brand-700)]" to="/app/creation">
                进入创作中心
              </Link>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              {creativeEntries.map((entry) => (
                <CreativeEntryCard {...entry} key={entry.to} />
              ))}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
