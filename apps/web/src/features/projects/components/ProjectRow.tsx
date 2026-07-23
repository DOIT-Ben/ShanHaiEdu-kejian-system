import { Archive, ArrowRight, CircleDot, CircleHelp, Clock3, FilePenLine } from "lucide-react";
import { Link } from "react-router-dom";
import type { ProjectSummary } from "@/entities/project/model";

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

export function ProjectRow({ project }: { project: ProjectSummary }) {
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
