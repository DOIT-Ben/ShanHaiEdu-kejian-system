import { ArrowRight, BookOpen, Clock3, FolderPlus, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useProjectsQuery } from "@/features/projects/hooks/useProjectsQuery";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export function ProjectsPage() {
  const projectQuery = useProjectsQuery();
  const [search, setSearch] = useState("");
  const visibleProjects = projectQuery.data ?? [];
  const filteredProjects = visibleProjects.filter((project) =>
    project.title
      .concat(" ", project.knowledgePoint)
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  return (
    <div className="mx-auto max-w-[1440px] px-4 py-4 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link className={buttonVariants()} to="/app/projects/new">
            <FolderPlus aria-hidden="true" />
            创建项目
          </Link>
        }
        description="一个项目对应一个小知识点教材，课时、教案和课堂作品都保留在这里。"
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
        <div className="mt-6 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-4 text-sm text-[var(--sh-danger)]">
          项目列表暂时无法加载，请检查网络后重试。
        </div>
      ) : null}
      {projectQuery.isLoading ? (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3" role="status">
          <span className="sr-only">正在读取你的项目</span>
          {Array.from({ length: 3 }, (_, index) => (
            <span
              aria-hidden="true"
              className="h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
              key={index}
            />
          ))}
        </div>
      ) : null}
      <div
        className={
          projectQuery.isLoading ? "hidden" : "mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3"
        }
        aria-busy={projectQuery.isFetching}
      >
        {filteredProjects.map((project, index) => (
          <article
            className="group overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] transition-[transform,border-color,box-shadow] duration-[var(--sh-duration-normal)] hover:-translate-y-0.5 hover:border-[var(--sh-brand-300)] hover:shadow-[var(--sh-shadow-card)]"
            key={project.id}
          >
            <div
              className={
                index === 0
                  ? "h-2 bg-[var(--sh-brand-500)]"
                  : index === 1
                    ? "h-2 bg-[var(--sh-success)]"
                    : "h-2 bg-[var(--sh-warning)]"
              }
            />
            <div className="p-5">
              <div className="flex items-start justify-between gap-4">
                <span className="grid size-11 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                  <BookOpen aria-hidden="true" className="size-5" />
                </span>
                <span className="rounded-full bg-[var(--sh-warning-soft)] px-2.5 py-1 text-xs font-semibold text-[var(--sh-warning)]">
                  {project.progressLabel}
                </span>
              </div>
              <h2 className="mt-3 text-lg font-bold text-[var(--sh-ink-strong)]">
                {project.title}
              </h2>
              <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                {project.grade} · {project.textbookEdition}
              </p>
              <p className="mt-3 line-clamp-2 text-sm font-medium text-[var(--sh-ink-default)]">
                {project.currentLesson ?? project.knowledgePoint}
              </p>
              {project.nextAction ? (
                <div className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-3">
                  <p className="text-xs font-semibold text-[var(--sh-brand-600)]">下一件事</p>
                  <p className="mt-1 text-sm text-[var(--sh-ink-strong)]">{project.nextAction}</p>
                </div>
              ) : null}
              <div className="mt-4 flex items-center justify-between gap-3">
                <span className="flex items-center gap-1.5 text-xs text-[var(--sh-ink-faint)]">
                  <Clock3 aria-hidden="true" className="size-3.5" />
                  {project.updatedAt}
                </span>
                <Link
                  className="inline-flex items-center gap-1 text-sm font-semibold text-[var(--sh-brand-600)]"
                  to={`/app/projects/${project.id}`}
                >
                  {project.archived ? "查看项目" : "继续制作"}
                  <ArrowRight
                    aria-hidden="true"
                    className="size-4 transition-transform group-hover:translate-x-0.5"
                  />
                </Link>
              </div>
            </div>
          </article>
        ))}
      </div>
      {!projectQuery.isLoading && !projectQuery.isError && filteredProjects.length === 0 ? (
        <p className="mt-7 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-8 text-center text-sm text-[var(--sh-ink-muted)]">
          {search.trim() ? "没有找到匹配的项目，请调整搜索词。" : "还没有项目，从一份教材开始吧。"}
        </p>
      ) : null}
      {projectQuery.hasNextPage ? (
        <div className="mt-7 text-center">
          <button
            className="rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-4 py-2 text-sm font-semibold text-[var(--sh-brand-700)] hover:bg-[var(--sh-brand-50)] disabled:cursor-wait disabled:opacity-60"
            disabled={projectQuery.isFetchingNextPage}
            onClick={() => void projectQuery.fetchNextPage()}
            type="button"
          >
            {projectQuery.isFetchingNextPage ? "正在读取更多项目" : "加载更多项目"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
