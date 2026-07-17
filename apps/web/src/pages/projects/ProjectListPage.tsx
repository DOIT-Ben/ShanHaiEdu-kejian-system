import { Link } from "react-router";
import { FolderOpen, Plus } from "lucide-react";
import { useProjects } from "@/features/projects";
import { formatRelativeTime } from "@/shared/lib/format";
import { Badge, Button, EmptyState, PageHeader, Skeleton } from "@/shared/ui";

const MODE_LABELS: Record<string, string> = {
  manual: "手动模式",
  assisted: "半自动模式",
  automatic: "全自动模式",
};

const STATUS_LABELS: Record<string, { label: string; tone: "neutral" | "brand" | "success" }> = {
  draft: { label: "准备中", tone: "neutral" },
  active: { label: "创作中", tone: "brand" },
  completed: { label: "已完成", tone: "success" },
  archived: { label: "已归档", tone: "neutral" },
};

export default function ProjectListPage() {
  const { data: projects, isPending } = useProjects();

  return (
    <div className="mx-auto w-full max-w-[var(--sh-content-max)] px-6 py-8">
      <PageHeader
        title="项目"
        description="一个项目对应一个知识点，包含多个课时的完整课堂作品。"
        actions={
          <Button asChild>
            <Link to="/app/projects/new">
              <Plus className="size-4" aria-hidden />
              上传教材，创建项目
            </Link>
          </Button>
        }
      />
      {isPending ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-36 rounded-lg" />
          ))}
        </div>
      ) : projects && projects.length > 0 ? (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {projects.map((project) => {
            const status = STATUS_LABELS[project.status] ?? { label: project.status, tone: "neutral" as const };
            return (
              <li key={project.id}>
                <Link
                  to={`/app/projects/${project.id}`}
                  className="flex h-full flex-col rounded-lg border border-line-subtle bg-surface p-5 shadow-card transition-shadow duration-150 hover:shadow-floating"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="min-w-0 truncate text-base font-semibold text-ink-strong">
                      {project.title}
                    </h2>
                    <Badge tone={status.tone}>{status.label}</Badge>
                  </div>
                  <p className="mt-1.5 text-sm text-ink-muted">
                    知识点：{project.knowledge_point}
                  </p>
                  <div className="mt-auto flex items-center justify-between pt-4 text-xs text-ink-faint">
                    <span>{MODE_LABELS[project.automation_mode] ?? project.automation_mode}</span>
                    <span>{formatRelativeTime(project.updated_at)}更新</span>
                  </div>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          className="mt-6"
          icon={<FolderOpen className="size-8" aria-hidden />}
          title="还没有项目"
          description="上传一份教材，山海会陪你把它变成完整的课堂作品。"
          action={
            <Button asChild>
              <Link to="/app/projects/new">上传教材，创建项目</Link>
            </Button>
          }
        />
      )}
    </div>
  );
}
