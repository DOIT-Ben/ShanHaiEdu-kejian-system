import type { ComponentType } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { LockKeyhole } from "lucide-react";
import { FineStoryboardStep } from "@/features/workbench/renderers/FineStoryboardStep";
import { FinalVideoStep } from "@/features/workbench/renderers/FinalVideoStep";
import { IntroOptionsStep } from "@/features/workbench/renderers/IntroOptionsStep";
import { LessonPlanStep } from "@/features/workbench/renderers/LessonPlanStep";
import { MasterScriptStep } from "@/features/workbench/renderers/MasterScriptStep";
import { PptCoverStep } from "@/features/workbench/renderers/PptCoverStep";
import { PptExportStep } from "@/features/workbench/renderers/PptExportStep";
import { PptOutlineStep } from "@/features/workbench/renderers/PptOutlineStep";
import { PptPagesStep } from "@/features/workbench/renderers/PptPagesStep";
import { PreparationStep } from "@/features/workbench/renderers/PreparationStep";
import { RoughStoryboardStep } from "@/features/workbench/renderers/RoughStoryboardStep";
import { VideoAssetsStep } from "@/features/workbench/renderers/VideoAssetsStep";
import { VideoStyleStep } from "@/features/workbench/renderers/VideoStyleStep";
import { ScenarioStateNotice } from "@/features/workbench/components/ScenarioStateNotice";
import { getWorkbenchStepBlocker } from "@/features/workbench/lib/stepAccess";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { useMockRuntime } from "@/shared/api/mocks/runtime";
import { EmptyState } from "@/shared/ui/EmptyState";
import { buttonVariants } from "@/shared/ui/Button";

const MaterialsStep = () => <PreparationStep type="materials" />;
const LessonDivisionStep = () => <PreparationStep type="lesson-division" />;

const nodeRendererRegistry: Record<string, ComponentType> = {
  materials: MaterialsStep,
  "lesson-division": LessonDivisionStep,
  "lesson-plan": LessonPlanStep,
  "lesson-plan-review": LessonPlanStep,
  "intro-options": IntroOptionsStep,
  "intro-selection": IntroOptionsStep,
  "ppt-outline": PptOutlineStep,
  "ppt-cover": PptCoverStep,
  "ppt-pages": PptPagesStep,
  "ppt-export": PptExportStep,
  "master-script": MasterScriptStep,
  "rough-storyboard": RoughStoryboardStep,
  "video-style": VideoStyleStep,
  "video-assets": VideoAssetsStep,
  "fine-storyboard": FineStoryboardStep,
  "final-video": FinalVideoStep,
};

const projectScopedSteps = new Set(["materials", "lesson-division"]);

export function WorkStepPage() {
  const { lessonId = "", projectId = "", stepKey = "lesson-plan" } = useParams();
  const [searchParams] = useSearchParams();
  const runtime = useMockRuntime();
  const scenario = searchParams.get("scenario");
  const Renderer = nodeRendererRegistry[stepKey];
  if (scenario === "forbidden") {
    return (
      <EmptyState
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}`}
          >
            返回项目
          </Link>
        }
        description="你当前没有查看或修改这项作品的权限。如需继续，请联系项目负责人调整权限。"
        icon={LockKeyhole}
        title="没有访问权限"
      />
    );
  }
  if (!Renderer) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-bold text-[var(--sh-ink-strong)]">此制作步骤需要升级</h1>
        <p className="mt-3 text-[var(--sh-ink-muted)]">
          暂时无法打开“{stepKey}”。刷新后仍未恢复，请联系学校管理员。
        </p>
      </div>
    );
  }
  const lessonExists = getApprovedProjectLessons(runtime, projectId).some(
    (lesson) => lesson.id === lessonId,
  );
  if (!projectScopedSteps.has(stepKey) && !lessonExists) {
    return (
      <EmptyState
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}/materials`}
          >
            返回课时安排
          </Link>
        }
        description="这个课时不在当前已批准的课时安排中，请返回核对后再继续。"
        icon={LockKeyhole}
        title="找不到这个课时"
      />
    );
  }
  const blocker = getWorkbenchStepBlocker(runtime, projectId, lessonId, stepKey);
  if (blocker) {
    return (
      <EmptyState
        action={
          <Link
            className={buttonVariants()}
            to={`/app/projects/${projectId}/lessons/${lessonId}/work/${blocker.toStep}`}
          >
            {blocker.actionLabel}
          </Link>
        }
        description="完成前一步并确认后，这项内容会自动解锁。"
        icon={LockKeyhole}
        title={blocker.title}
      />
    );
  }
  return (
    <div
      data-step-key={stepKey}
      data-testid="work-step-content"
      key={`${projectId}:${lessonId}:${stepKey}`}
    >
      <ScenarioStateNotice scenario={scenario} />
      <Renderer />
    </div>
  );
}
