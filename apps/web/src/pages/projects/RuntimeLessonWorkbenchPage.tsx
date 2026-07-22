import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, CircleDashed, Clock3, TriangleAlert } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getLesson } from "@/features/lessons/api/lessonsApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { getProjectWorkflow } from "@/features/workflow/api/workflowApi";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const stepLabels: Record<string, string> = {
  lesson_plan: "教案",
  intro_options: "课堂导入",
  ppt: "课堂 PPT",
  video: "课堂视频",
};

const nodeStatusLabels: Record<string, string> = {
  not_started: "未开始",
  ready: "待开始",
  queued: "等待处理",
  running: "正在处理",
  succeeded: "已完成",
  failed: "处理失败",
  cancelled: "已取消",
  paused: "已暂停",
  stale: "内容已变化",
};

function nodeStatusIcon(status: string) {
  if (status === "succeeded") return <CheckCircle2 aria-hidden="true" className="size-4" />;
  if (["failed", "stale"].includes(status)) {
    return <TriangleAlert aria-hidden="true" className="size-4" />;
  }
  if (["running", "queued", "paused"].includes(status)) {
    return <Clock3 aria-hidden="true" className="size-4" />;
  }
  return <CircleDashed aria-hidden="true" className="size-4" />;
}

function nodeStatusClass(status: string) {
  if (status === "succeeded") return "text-[var(--sh-success)] bg-[var(--sh-success-soft)]";
  if (["failed", "stale"].includes(status))
    return "text-[var(--sh-danger)] bg-[var(--sh-danger-soft)]";
  if (["running", "queued", "paused"].includes(status)) {
    return "text-[var(--sh-action-primary)] bg-[var(--sh-brand-50)]";
  }
  return "text-[var(--sh-ink-muted)] bg-[var(--sh-surface-soft)]";
}

export function RuntimeLessonWorkbenchPage() {
  const { lessonId, projectId, stepKey = "lesson_plan" } = useParams();
  useProjectEvents(projectId);

  const projectQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProject(projectId ?? ""),
    queryKey: projectKeys.detail(projectId ?? ""),
  });
  const lessonQuery = useQuery({
    enabled: Boolean(lessonId),
    queryFn: () => getLesson(lessonId ?? ""),
    queryKey: ["lessons", lessonId],
  });
  const workflowQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProjectWorkflow(projectId ?? ""),
    queryKey: ["projects", projectId, "workflow"],
  });

  if (!projectId || !lessonId) return null;
  if (projectQuery.isLoading || lessonQuery.isLoading || workflowQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-8 md:px-6" role="status">
        <div className="h-44 animate-pulse rounded-[var(--sh-radius-lg)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
        <span className="sr-only">正在读取课时工作台</span>
      </div>
    );
  }
  if (projectQuery.isError || lessonQuery.isError || workflowQuery.isError) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-8 md:px-6">
        <FocusPageHeader
          description="服务端暂时没有返回这节课时的完整数据。"
          title="暂时无法打开课时"
        />
        <Link className={buttonVariants({ className: "mt-6" })} to={`/app/projects/${projectId}`}>
          <ArrowLeft aria-hidden="true" />
          返回项目
        </Link>
      </div>
    );
  }

  const project = projectQuery.data;
  const lesson = lessonQuery.data?.lesson;
  const workflow = workflowQuery.data;
  if (!project || !lesson || !workflow) return null;

  const currentBranch = lesson.branches.find((branch) => branch.branch_key === stepKey);
  const nodeRuns = workflow.node_runs.filter((node) => {
    const normalizedKey = node.node_key.toLowerCase();
    return (
      normalizedKey.includes(stepKey.toLowerCase()) ||
      normalizedKey.includes(lesson.lesson_key.toLowerCase())
    );
  });

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}`}
          >
            <ArrowLeft aria-hidden="true" />
            返回项目
          </Link>
        }
        description={`${project.title} · ${lesson.title} · ${stepLabels[stepKey] ?? stepKey}`}
        title={`${lesson.title} · ${stepLabels[stepKey] ?? "当前步骤"}`}
      />

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section aria-labelledby="runtime-workbench-title" className="min-w-0">
          <div className="rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)] md:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-[var(--sh-ink-faint)]">
                  当前课时
                </p>
                <h2
                  className="mt-2 text-xl font-semibold text-[var(--sh-ink-strong)]"
                  id="runtime-workbench-title"
                >
                  {lesson.title}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--sh-ink-muted)]">
                  {lesson.objective_summary || lesson.scope_summary}
                </p>
              </div>
              <span className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 py-1.5 text-xs text-[var(--sh-ink-muted)]">
                {lesson.estimated_minutes
                  ? `${String(lesson.estimated_minutes)} 分钟`
                  : "课时已建立"}
              </span>
            </div>

            <div className="mt-6 border-t border-[var(--sh-line-subtle)] pt-5">
              <h3 className="text-sm font-semibold text-[var(--sh-ink-strong)]">服务端当前状态</h3>
              {nodeRuns.length ? (
                <ul className="mt-3 grid gap-2" aria-label="当前节点状态">
                  {nodeRuns.map((node) => (
                    <li
                      className="flex items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] px-3 py-3"
                      key={node.id}
                    >
                      <span className="min-w-0 truncate text-sm text-[var(--sh-ink-strong)]">
                        {node.title || node.node_key}
                      </span>
                      <span
                        className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ${nodeStatusClass(node.status)}`}
                      >
                        {nodeStatusIcon(node.status)}
                        {nodeStatusLabels[node.status] ?? node.status}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 py-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
                  这一步还没有服务端节点记录。先完成上游确认，系统才会创建可执行的制作任务。
                </p>
              )}
            </div>
          </div>
        </section>

        <aside className="h-fit rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">课时分支</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
            选择要查看的课时成果分支，项目和课时上下文会保持不变。
          </p>
          <nav aria-label="课时分支" className="mt-4 grid gap-1.5">
            {lesson.branches.map((branch) => (
              <Link
                className={`flex items-center justify-between rounded-[var(--sh-radius-sm)] px-3 py-2.5 text-sm transition-colors ${branch.branch_key === stepKey ? "bg-[var(--sh-brand-50)] font-medium text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"}`}
                key={branch.branch_key}
                to={`/app/projects/${projectId}/lessons/${lesson.id}/work/${branch.branch_key}`}
              >
                <span>{stepLabels[branch.branch_key] ?? branch.branch_key}</span>
                <span className="text-xs">{branch.enabled ? "可用" : "未启用"}</span>
              </Link>
            ))}
          </nav>
          {currentBranch && !currentBranch.enabled ? (
            <p className="mt-4 text-xs leading-5 text-[var(--sh-ink-muted)]">
              该分支当前未启用，不会创建新的制作任务。
            </p>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
