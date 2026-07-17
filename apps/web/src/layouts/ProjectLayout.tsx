import { NavLink, Outlet, useParams } from "react-router";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { useProjectWorkflow } from "@/features/projects";
import { cn } from "@/shared/lib/cn";
import { Badge, Skeleton } from "@/shared/ui";

/**
 * 项目上下文骨架（02 §2）：56px 项目上下文条 + 项目内导航。
 * 项目总览｜教材与课时｜课时工作台｜素材与成果｜项目任务｜项目交付。
 */

const MODE_LABELS: Record<string, string> = {
  manual: "手动",
  assisted: "半自动",
  automatic: "全自动",
};

export default function ProjectLayout() {
  const { projectId = "" } = useParams();
  const { data, isPending } = useProjectWorkflow(projectId);
  const project = data?.project;

  const navItems = [
    { to: `/app/projects/${projectId}`, label: "项目总览", end: true },
    { to: `/app/projects/${projectId}/materials`, label: "教材与课时", end: false },
    { to: `/app/projects/${projectId}/lessons`, label: "课时工作台", end: false },
    { to: `/app/projects/${projectId}/results`, label: "素材与成果", end: false },
    { to: `/app/projects/${projectId}/tasks`, label: "项目任务", end: false },
    { to: `/app/projects/${projectId}/delivery`, label: "项目交付", end: false },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="sticky top-16 z-30 border-b border-line-subtle bg-surface">
        <div className="mx-auto flex h-14 max-w-[var(--sh-content-max)] items-center gap-3 px-6">
          <nav aria-label="面包屑" className="flex min-w-0 items-center gap-1.5 text-sm">
            <Link to="/app/projects" className="shrink-0 text-ink-muted hover:text-ink-strong">
              项目
            </Link>
            <ChevronRight className="size-3.5 shrink-0 text-ink-faint" aria-hidden />
            {isPending ? (
              <Skeleton className="h-4 w-32" />
            ) : (
              <span className="truncate font-medium text-ink-strong">{project?.title ?? "项目"}</span>
            )}
          </nav>
          {project ? (
            <Badge tone="neutral" className="shrink-0">
              {MODE_LABELS[project.automation_mode] ?? project.automation_mode}模式
            </Badge>
          ) : null}
          <nav aria-label="项目导航" className="ml-auto flex items-center gap-1 overflow-x-auto">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                    isActive
                      ? "bg-brand-50 text-brand-600"
                      : "text-ink-muted hover:bg-surface-soft hover:text-ink-strong",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
