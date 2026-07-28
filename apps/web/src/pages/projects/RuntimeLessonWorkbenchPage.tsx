import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { IntroOptionsWorkflowPanel } from "@/features/intro-options/components/IntroOptionsWorkflowPanel";
import { getLesson } from "@/features/lessons/api/lessonsApi";
import { LessonPlanWorkflowPanel } from "@/features/lessons/components/LessonPlanWorkflowPanel";
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

const workbenchSteps = ["lesson_plan", "intro_options", "ppt", "video"] as const;
const availableSteps = new Set(["lesson_plan", "intro_options"]);

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

  const branchByKey = new Map(lesson.branches.map((branch) => [branch.branch_key, branch]));
  const branches = workbenchSteps.map((key) => ({
    available: availableSteps.has(key),
    enabled: branchByKey.get(key)?.enabled ?? false,
    key,
    label: stepLabels[key] ?? "当前步骤",
    to: `/app/projects/${projectId}/lessons/${lesson.id}/work/${key}`,
  }));
  const unavailableStep = !availableSteps.has(branchKey);

  return (
    <div className="mx-auto max-w-[1480px] px-3 py-4 sm:px-4 md:px-6 lg:px-8">
      <header className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <div className="flex min-w-0 flex-wrap items-center gap-3">
            <h1 className="break-words text-[22px] font-semibold leading-tight text-[var(--sh-ink-strong)] md:text-[24px]">
              {lesson.title}
            </h1>
            <span className="rounded-[var(--sh-radius-control)] bg-[var(--sh-brand-50)] px-2.5 py-1 text-xs font-semibold text-[var(--sh-brand-700)]">
              {stepLabel}
            </span>
          </div>
          <p className="mt-1 truncate text-xs leading-5 text-[var(--sh-ink-muted)] md:text-sm">
            {project.title}
          </p>
        </div>
        <Link
          aria-label="返回项目"
          className={buttonVariants({ className: "min-h-11", variant: "secondary" })}
          to={`/app/projects/${projectId}`}
        >
          <ArrowLeft aria-hidden="true" />
          <span className="hidden min-[480px]:inline">返回项目</span>
        </Link>
      </header>
      <div className="mt-4">
        <LessonWorkbenchSummary
          branches={branches}
          currentBranchKey={branchKey}
          durationLabel={
            lesson.estimated_minutes ? `${String(lesson.estimated_minutes)} 分钟` : "课时已建立"
          }
          objective={lesson.objective_summary || lesson.scope_summary}
        />
        {branchKey === "lesson_plan" ? (
          <LessonPlanWorkflowPanel lessonId={lessonId} projectId={projectId} />
        ) : null}
        {branchKey === "intro_options" ? (
          <IntroOptionsWorkflowPanel lessonId={lessonId} projectId={projectId} />
        ) : null}
        {unavailableStep ? (
          <section
            aria-labelledby="unavailable-step-title"
            className="border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] px-5 py-10 md:px-8"
          >
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">后续制作步骤</p>
            <h2
              className="mt-2 text-lg font-semibold text-[var(--sh-ink-strong)]"
              id="unavailable-step-title"
            >
              {stepLabel} 尚未开放
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--sh-ink-muted)]">
              当前阶段先完成教案与课堂导入。该步骤开放后会继续使用本课时已经批准的内容。
            </p>
          </section>
        ) : null}
      </div>
    </div>
  );
}
