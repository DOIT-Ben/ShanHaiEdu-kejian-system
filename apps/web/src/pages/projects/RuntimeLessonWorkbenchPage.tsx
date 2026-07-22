import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getLesson } from "@/features/lessons/api/lessonsApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { getProjectWorkflow } from "@/features/workflow/api/workflowApi";
import { LessonWorkbenchSummary } from "@/features/workbench/components/LessonWorkbenchSummary";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const stepLabels: Record<string, string> = {
  lesson_plan: "教案",
  intro_options: "课堂导入",
  ppt: "课堂 PPT",
  video: "课堂视频",
};

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
          description="这节课的数据暂时没有读取完整，请检查网络后重试。"
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
      <div className="mt-5">
        <LessonWorkbenchSummary
          branches={lesson.branches.map((branch) => ({
            enabled: branch.enabled,
            key: branch.branch_key,
            label: stepLabels[branch.branch_key] ?? branch.branch_key,
            to: `/app/projects/${projectId}/lessons/${lesson.id}/work/${branch.branch_key}`,
          }))}
          currentBranchKey={stepKey}
          durationLabel={
            lesson.estimated_minutes ? `${String(lesson.estimated_minutes)} 分钟` : "课时已建立"
          }
          lessonTitle={lesson.title}
          objective={lesson.objective_summary || lesson.scope_summary}
          statuses={nodeRuns.map((node) => ({
            id: node.id,
            status: node.status,
            title: node.title || node.node_key,
          }))}
        />
      </div>
    </div>
  );
}
