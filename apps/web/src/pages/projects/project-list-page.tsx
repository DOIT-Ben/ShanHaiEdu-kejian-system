import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { Archive, ArchiveRestore, FolderPlus, Search } from "lucide-react";
import { useArchiveProject, useProjects, useRestoreProject, type ProjectListFilters } from "@/features/projects";
import { useDebouncedCallback } from "@/shared/hooks";
import { formatMinorUnits, formatRelativeTime } from "@/shared/lib/format";
import type { Project } from "@/shared/api/types";
import {
  Badge,
  Button,
  EmptyState,
  Input,
  PageHeader,
  Progress,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  toast,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const STATUS_LABEL: Record<Project["status"], { label: string; tone: "neutral" | "brand" | "warning" }> = {
  draft: { label: "草稿", tone: "neutral" },
  active: { label: "进行中", tone: "brand" },
  archived: { label: "已归档", tone: "warning" },
};

const EXECUTION_LABEL: Record<Project["execution_mode"], string> = {
  manual: "手动模式",
  semi_auto: "半自动模式",
  full_auto_draft: "全自动草稿模式",
};

function ProjectCard({ project, onArchive, onRestore }: { project: Project; onArchive: () => void; onRestore: () => void }) {
  const status = STATUS_LABEL[project.status];
  return (
    <div className="group relative rounded-card border border-line bg-surface-1 p-4 transition-shadow hover:shadow-sm">
      <Link to={`/app/projects/${project.project_id}`} className="absolute inset-0" aria-label={`打开项目 ${project.name}`} />
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-sm font-semibold text-ink-1">{project.name}</h3>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <p className="mt-1 text-xs text-ink-muted">
        {project.grade}年级 · {project.textbook_version ?? "未选教材"} {project.volume ?? ""} · {EXECUTION_LABEL[project.execution_mode]}
      </p>
      <div className="mt-3">
        <div className="flex items-center justify-between text-xs text-ink-2">
          <span>{project.lesson_count ?? 0} 个课时</span>
          <span>{Math.round(project.progress_percent ?? 0)}%</span>
        </div>
        <Progress className="mt-1" value={project.progress_percent ?? 0} />
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-ink-muted">
        <span>
          预算 {formatMinorUnits(project.budget_minor_units ?? 0)} · 已用 {formatMinorUnits(project.spent_minor_units ?? 0)}
        </span>
        <span>更新于 {formatRelativeTime(project.updated_at)}</span>
      </div>
      <div className="relative z-10 mt-3 hidden justify-end gap-1 group-hover:flex">
        {project.status === "archived" ? (
          <Button size="sm" variant="ghost" onClick={onRestore}>
            <ArchiveRestore className="size-3.5" aria-hidden />
            恢复
          </Button>
        ) : (
          <Button size="sm" variant="ghost" onClick={onArchive}>
            <Archive className="size-3.5" aria-hidden />
            归档
          </Button>
        )}
      </div>
    </div>
  );
}

export function ProjectListPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<ProjectListFilters>({ sort: "updated_desc" });
  const [keywordInput, setKeywordInput] = useState("");
  const projects = useProjects(filters);
  const archive = useArchiveProject();
  const restore = useRestoreProject();
  const debouncedKeyword = useDebouncedCallback((keyword: string) => {
    setFilters((prev) => ({ ...prev, keyword: keyword || undefined }));
  }, 300);

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="项目"
        description="每个项目对应一个教学单元的课件制作。"
        actions={
          <Button onClick={() => void navigate("/app/projects/new")}>
            <FolderPlus className="size-4" aria-hidden />
            新建项目
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <Input
            className="pl-8"
            placeholder="搜索项目名称"
            value={keywordInput}
            onChange={(event) => {
              setKeywordInput(event.target.value);
              debouncedKeyword.run(event.target.value);
            }}
          />
        </div>
        <Select
          value={filters.status ?? "all"}
          onValueChange={(value) =>
            setFilters((prev) => ({ ...prev, status: value === "all" ? undefined : (value as ProjectListFilters["status"]) }))
          }
        >
          <SelectTrigger className="w-32" aria-label="按状态筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="active">进行中</SelectItem>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="archived">已归档</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={filters.sort ?? "updated_desc"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, sort: value as ProjectListFilters["sort"] }))}
        >
          <SelectTrigger className="w-36" aria-label="排序方式">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="updated_desc">最近更新</SelectItem>
            <SelectItem value="created_desc">最近创建</SelectItem>
            <SelectItem value="name_asc">名称 A-Z</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {projects.isPending ? (
        <div className="grid gap-4 xl:grid-cols-3 lg:grid-cols-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-44" />
          ))}
        </div>
      ) : projects.isError ? (
        <AppErrorPanel error={projects.error} title="项目列表加载失败" onRetry={() => void projects.refetch()} />
      ) : projects.data.length === 0 ? (
        <EmptyState
          title={filters.keyword || filters.status ? "没有符合条件的项目" : "还没有项目"}
          description={filters.keyword || filters.status ? "调整筛选条件再试试。" : "创建第一个课件项目，上传教材开始备课。"}
          action={
            !filters.keyword && !filters.status ? (
              <Button onClick={() => void navigate("/app/projects/new")}>
                <FolderPlus className="size-4" aria-hidden />
                新建项目
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-3 lg:grid-cols-2">
          {projects.data.map((project) => (
            <ProjectCard
              key={project.project_id}
              project={project}
              onArchive={() => {
                archive.mutate(project.project_id, {
                  onSuccess: () => toast({ tone: "success", title: "项目已归档", description: "可在「已归档」筛选中找到并恢复。" }),
                });
              }}
              onRestore={() => {
                restore.mutate(project.project_id, {
                  onSuccess: () => toast({ tone: "success", title: "项目已恢复" }),
                });
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
