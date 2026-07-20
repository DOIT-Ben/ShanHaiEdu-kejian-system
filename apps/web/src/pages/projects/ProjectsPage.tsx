import {
  Archive,
  ArrowRight,
  CircleDot,
  CircleHelp,
  Clock3,
  FilePenLine,
  FolderPlus,
  Search,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { ProjectSummary } from "@/entities/project/model";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

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

function ProjectStatus({ project }: { project: ProjectSummary }) {
  const status =
    project.archived || project.status === "archived"
      ? { Icon: Archive, label: "已归档", className: "text-[var(--sh-ink-muted)]" }
      : project.status === "draft"
        ? { Icon: FilePenLine, label: "草稿", className: "text-[var(--sh-ink-muted)]" }
        : project.status === "active"
          ? { Icon: CircleDot, label: "进行中", className: "text-[var(--sh-brand-700)]" }
          : { Icon: CircleHelp, label: "状态待确认", className: "text-[var(--sh-ink-muted)]" };
  const { Icon } = status;
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${status.className}`}>
      <Icon aria-hidden="true" className="size-4 shrink-0" />
      {status.label}
    </span>
  );
}

function ProjectRow({ project }: { project: ProjectSummary }) {
  const nextAction = project.nextAction ?? (project.archived ? "查看项目成果" : "打开项目");
  return (
    <article
      aria-label={project.title}
      className="grid min-w-0 gap-3 border-b border-[var(--sh-line-subtle)] px-4 py-3 last:border-b-0 hover:bg-[var(--sh-surface-soft)] lg:grid-cols-[minmax(190px,1.15fr)_minmax(170px,1fr)_110px_minmax(180px,1.2fr)_88px_92px] lg:items-center lg:gap-4"
      data-testid="project-row"
    >
      <div className="min-w-0">
        <span className="mb-1 block text-[11px] font-medium text-[var(--sh-ink-faint)] lg:hidden">
          课题
        </span>
        <h2 className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
          {project.title}
        </h2>
        <p className="mt-0.5 truncate text-xs text-[var(--sh-ink-muted)]">
          {project.grade} · {project.textbookEdition}
        </p>
      </div>

      <div className="min-w-0">
        <span className="mb-1 block text-[11px] font-medium text-[var(--sh-ink-faint)] lg:hidden">
          当前课时
        </span>
        <p className="truncate text-sm text-[var(--sh-ink-default)]">
          {project.currentLesson ?? project.knowledgePoint}
        </p>
      </div>

      <div>
        <span className="mb-1 block text-[11px] font-medium text-[var(--sh-ink-faint)] lg:hidden">
          状态
        </span>
        <ProjectStatus project={project} />
      </div>

      <div className="min-w-0">
        <span className="mb-1 block text-[11px] font-medium text-[var(--sh-ink-faint)] lg:hidden">
          下一步
        </span>
        <p className="truncate text-sm text-[var(--sh-ink-default)]">{nextAction}</p>
      </div>

      <div className="flex items-center gap-1.5 text-xs text-[var(--sh-ink-faint)]">
        <Clock3 aria-hidden="true" className="size-3.5 shrink-0" />
        <span>{project.updatedAt}</span>
      </div>

      <Link
        aria-label={`${project.archived ? "查看" : "继续制作"}${project.title}`}
        className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--sh-brand-700)] lg:justify-self-end"
        to={`/app/projects/${project.id}`}
      >
        {project.archived ? "查看" : "继续制作"}
        <ArrowRight aria-hidden="true" className="size-4" />
      </Link>
    </article>
  );
}

export function ProjectsPage() {
  const projectQuery = useProjectsQuery();
  const [search, setSearch] = useState("");
  const visibleProjects = sortByRecentActivity(projectQuery.data ?? []);
  const normalizedSearch = search.trim().toLowerCase();
  const filteredProjects = visibleProjects.filter((project) =>
    [project.title, project.knowledgePoint, project.currentLesson, project.nextAction]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedSearch),
  );

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-4 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link className={buttonVariants({ size: "sm" })} to="/app/projects/new">
            <FolderPlus aria-hidden="true" />
            创建项目
          </Link>
        }
        supporting={
          <div className="flex min-h-10 w-full items-center gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 focus-within:border-[var(--sh-brand-300)] focus-within:shadow-[var(--sh-shadow-focus)]">
            <Search aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
            <input
              aria-label="搜索项目"
              className="min-h-10 min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-[var(--sh-ink-faint)]"
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索项目或知识点"
              type="search"
              value={search}
            />
          </div>
        }
        title="我的项目"
      />

      {projectQuery.isError ? (
        <div className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-3 text-sm text-[var(--sh-danger)]">
          项目列表暂时无法加载，请检查网络后重试。
        </div>
      ) : null}

      {projectQuery.isLoading ? (
        <div
          aria-label="正在读取项目"
          className="mt-4 overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
          role="status"
        >
          {Array.from({ length: 6 }, (_, index) => (
            <div
              aria-hidden="true"
              className="h-16 animate-pulse border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] last:border-b-0 motion-reduce:animate-none"
              key={index}
            />
          ))}
        </div>
      ) : null}

      {!projectQuery.isLoading ? (
        <div
          aria-busy={projectQuery.isFetching}
          className="mt-4 overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
          role="list"
        >
          <div className="hidden border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-soft)] px-4 py-2 text-[11px] font-semibold text-[var(--sh-ink-muted)] lg:grid lg:grid-cols-[minmax(190px,1.15fr)_minmax(170px,1fr)_110px_minmax(180px,1.2fr)_88px_92px] lg:items-center lg:gap-4">
            <span>课题</span>
            <span>当前课时</span>
            <span>状态</span>
            <span>下一步</span>
            <span>更新时间</span>
            <span className="sr-only">操作</span>
          </div>
          {filteredProjects.map((project) => (
            <div key={project.id} role="listitem">
              <ProjectRow project={project} />
            </div>
          ))}
        </div>
      ) : null}

      {!projectQuery.isLoading && !projectQuery.isError && filteredProjects.length === 0 ? (
        <p className="mt-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 text-center text-sm text-[var(--sh-ink-muted)]">
          {normalizedSearch
            ? "没有找到匹配的项目，请调整搜索词。"
            : "还没有项目，从一份教材开始吧。"}
        </p>
      ) : null}

      {projectQuery.hasNextPage ? (
        <div className="mt-5 text-center">
          <Button
            disabled={projectQuery.isFetchingNextPage}
            onClick={() => void projectQuery.fetchNextPage()}
            size="sm"
            variant="secondary"
          >
            {projectQuery.isFetchingNextPage ? "正在读取更多项目" : "加载更多项目"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
