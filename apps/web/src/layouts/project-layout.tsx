import { NavLink, Outlet, useParams } from "react-router";
import { useProject } from "@/features/projects";
import { useProjectEventStream } from "@/features/events";
import { cn } from "@/shared/lib/cn";
import { AppError } from "@/shared/api";
import { EmptyState, Spinner } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";
import type { Project } from "@/shared/api/types";

const PROJECT_NAV = [
  { to: "", label: "概览", end: true },
  { to: "textbook", label: "教材" },
  { to: "lesson-division", label: "课时划分" },
  { to: "lessons", label: "课时" },
  { to: "assets", label: "资产" },
  { to: "tasks", label: "任务" },
  { to: "delivery", label: "交付" },
  { to: "settings", label: "设置" },
];

export interface ProjectOutletContext {
  project: Project;
}

/** 项目容器：加载项目 + 建立项目级实时事件流 + 项目二级导航。 */
export function ProjectLayout() {
  const { projectId = "" } = useParams();
  const project = useProject(projectId);
  useProjectEventStream(project.data ? projectId : null);

  if (project.isPending) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner label="正在加载项目…" />
      </div>
    );
  }
  if (project.isError) {
    const error = project.error;
    if (error instanceof AppError && error.status === 404) {
      return (
        <div className="flex h-full items-center justify-center p-8">
          <EmptyState title="项目不存在" description="该项目可能已被删除，或你没有访问权限。" />
        </div>
      );
    }
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={error} title="项目加载失败" onRetry={() => void project.refetch()} />
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-line bg-surface-1 px-6">
        <nav className="-mb-px flex gap-1 overflow-x-auto" aria-label="项目导航">
          {PROJECT_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end ?? false}
              className={({ isActive }) =>
                cn(
                  "whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
                  isActive
                    ? "border-brand font-medium text-brand"
                    : "border-transparent text-ink-2 hover:border-line hover:text-ink-1",
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <Outlet context={{ project: project.data } satisfies ProjectOutletContext} />
      </div>
    </div>
  );
}
