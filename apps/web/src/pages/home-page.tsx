import { Link } from "react-router";
import { ArrowRight, Download, Eye, FolderPlus } from "lucide-react";
import { useHomeOverview } from "@/features/home";
import { useSession } from "@/features/session";
import { useDownloadFile } from "@/features/assets";
import { taskTitle } from "@/features/tasks";
import { getNodeDef } from "@/entities/workflow/nodes";
import { formatRelativeTime } from "@/shared/lib/format";
import type { TaskStatus } from "@/shared/lib/status";
import {
  Badge,
  Button,
  EmptyState,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Progress,
  Skeleton,
  TaskStatusBadge,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

/** 工作台首页：最近项目 / 待审核 / 进行中任务 / 最近交付。 */
export function HomePage() {
  const session = useSession();
  const overview = useHomeOverview();
  const download = useDownloadFile();

  if (overview.isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-56" />
          ))}
        </div>
      </div>
    );
  }
  if (overview.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={overview.error} title="首页加载失败" onRetry={() => void overview.refetch()} />
      </div>
    );
  }

  const data = overview.data;

  return (
    <div className="space-y-5 p-6">
      <PageHeader
        title={`${session.data?.user.display_name ?? ""}，欢迎回来`}
        description="从最近的项目继续，或处理等待你审核的内容。"
        actions={
          <Button asChild>
            <Link to="/app/projects/new">
              <FolderPlus className="size-4" aria-hidden />
              新建项目
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <PanelHeader
            title="最近项目"
            actions={
              <Link to="/app/projects" className="text-xs font-medium text-brand hover:underline">
                全部项目
              </Link>
            }
          />
          <PanelBody>
            {data.recent_projects.length === 0 ? (
              <EmptyState title="还没有项目" description="创建第一个课件项目，开始备课。" className="py-8" />
            ) : (
              <ul className="divide-y divide-divider">
                {data.recent_projects.map((project) => (
                  <li key={project.project_id}>
                    <Link
                      to={`/app/projects/${project.project_id}`}
                      className="flex items-center gap-3 py-2.5 transition-colors hover:bg-surface-hover"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-ink-1">{project.name}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">
                          {project.grade}年级 · {project.textbook_version ?? ""} · 更新于 {formatRelativeTime(project.updated_at)}
                        </p>
                      </div>
                      {typeof project.progress_percent === "number" ? (
                        <div className="w-28">
                          <Progress value={project.progress_percent} />
                        </div>
                      ) : null}
                      <ArrowRight className="size-4 shrink-0 text-ink-muted" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="等待你审核" />
          <PanelBody>
            {data.pending_reviews.length === 0 ? (
              <EmptyState title="暂无待审核内容" className="py-8" />
            ) : (
              <ul className="divide-y divide-divider">
                {data.pending_reviews.map((review) => (
                  <li key={review.review_id}>
                    <Link
                      to={
                        review.lesson_id
                          ? `/app/projects/${review.project_id}/lessons/${review.lesson_id}/workbench/${review.node_key}`
                          : `/app/projects/${review.project_id}/lesson-division`
                      }
                      className="flex items-center gap-3 py-2.5 transition-colors hover:bg-surface-hover"
                    >
                      <Eye className="size-4 shrink-0 text-warning" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm text-ink-1">{review.title}</p>
                        <p className="mt-0.5 text-xs text-ink-muted">
                          {review.project_name}
                          {review.lesson_title ? ` · ${review.lesson_title}` : ""} ·{" "}
                          {getNodeDef(review.node_key)?.title ?? review.node_key} · 等待 {formatRelativeTime(review.waiting_since)}
                        </p>
                      </div>
                      <ArrowRight className="size-4 shrink-0 text-ink-muted" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="进行中的任务" />
          <PanelBody>
            {data.running_tasks.length === 0 && data.failed_tasks.length === 0 ? (
              <EmptyState title="暂无任务" className="py-8" />
            ) : (
              <ul className="divide-y divide-divider">
                {[...data.running_tasks, ...data.failed_tasks].map((task) => (
                  <li key={task.task_id} className="flex items-center gap-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink-1">{taskTitle(task)}</p>
                      <p className="mt-0.5 text-xs text-ink-muted">{task.progress_message ?? formatRelativeTime(task.created_at)}</p>
                    </div>
                    {task.status === "running" ? <Progress className="w-24" value={task.progress_percent} /> : null}
                    <TaskStatusBadge status={task.status as TaskStatus} />
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader title="最近交付" />
          <PanelBody>
            {data.recent_deliveries.length === 0 ? (
              <EmptyState title="暂无交付记录" description="项目完成打包后会显示在这里。" className="py-8" />
            ) : (
              <ul className="divide-y divide-divider">
                {data.recent_deliveries.map((item) => (
                  <li key={`${item.project_id}-${item.delivered_at}`} className="flex items-center gap-3 py-2.5">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-ink-1">{item.project_name}</p>
                      <p className="mt-0.5 text-xs text-ink-muted">
                        {item.file_object.file_name} · {formatRelativeTime(item.delivered_at)}
                      </p>
                    </div>
                    <Badge tone="success">已交付</Badge>
                    <Button
                      size="sm"
                      variant="ghost"
                      loading={download.isPending}
                      onClick={() =>
                        download.mutate({ fileObjectId: item.file_object.file_object_id, fileName: item.file_object.file_name })
                      }
                    >
                      <Download className="size-3.5" aria-hidden />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
