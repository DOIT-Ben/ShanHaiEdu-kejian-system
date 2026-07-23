import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getLesson } from "@/features/lessons/api/lessonsApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
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
  const branchKey = stepKey.replaceAll("-", "_");
  const stepLabel = stepLabels[branchKey] ?? "当前步骤";

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
  const lesson = lessonQuery.data?.lesson;
  const lessonOwnedByProject = Boolean(projectId && lesson?.project_id === projectId);
  useProjectEvents(lessonOwnedByProject ? projectId : undefined);

  if (!projectId || !lessonId) return null;
  if (projectQuery.isLoading || lessonQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-8 md:px-6" role="status">
        <div className="h-44 animate-pulse rounded-[var(--sh-radius-lg)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
        <span className="sr-only">正在读取课时工作台</span>
      </div>
    );
  }
  if (projectQuery.isError || lessonQuery.isError) {
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

  if (lesson && !lessonOwnedByProject) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-8 md:px-6">
        <FocusPageHeader
          description="请返回当前项目，从课时列表重新进入。"
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
  if (!project || !lesson) return null;

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
        description={`${project.title} · ${lesson.title} · ${stepLabel}`}
        title={`${lesson.title} · ${stepLabel}`}
      />
      <div className="mt-5">
        <LessonWorkbenchSummary
          branches={lesson.branches.map((branch) => ({
            enabled: branch.enabled,
            key: branch.branch_key,
            label: stepLabels[branch.branch_key] ?? "其他制作分支",
            to: `/app/projects/${projectId}/lessons/${lesson.id}/work/${branch.branch_key}`,
          }))}
          currentBranchKey={branchKey}
          durationLabel={
            lesson.estimated_minutes ? `${String(lesson.estimated_minutes)} 分钟` : "课时已建立"
          }
          lessonTitle={lesson.title}
          objective={lesson.objective_summary || lesson.scope_summary}
          progressErrorMessage="这一步暂时没有可显示的制作进度。其他项目资料仍可继续查看和编辑。"
          progressState="error"
          statuses={[]}
        />
      </div>
    </div>
  );
}
