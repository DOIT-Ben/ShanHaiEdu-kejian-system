import type { WorkflowStatus } from "@/entities/workflow/model";
import { introOptions } from "@/features/intro-options/data";
import { isPreviewAdopted, readIntroOptionsDraft } from "@/features/intro-options/state";
import { readLessonList } from "@/features/workbench/lib/projectLessons";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

type StepRequirement = {
  actionLabel: string;
  dependencyKey: string;
  title: string;
  toStep: string;
};

const stepRequirements: Record<string, StepRequirement> = {
  "lesson-division": {
    actionLabel: "去查看教材",
    dependencyKey: "materials",
    title: "先准备教材",
    toStep: "materials",
  },
  "lesson-plan": {
    actionLabel: "去批准课时",
    dependencyKey: "lesson-division",
    title: "先批准课时安排",
    toStep: "lesson-division",
  },
  "lesson-plan-review": {
    actionLabel: "去批准课时",
    dependencyKey: "lesson-division",
    title: "先批准课时安排",
    toStep: "lesson-division",
  },
  "intro-options": {
    actionLabel: "去批准课时",
    dependencyKey: "lesson-division",
    title: "先批准课时安排",
    toStep: "lesson-division",
  },
  "intro-selection": {
    actionLabel: "去批准课时",
    dependencyKey: "lesson-division",
    title: "先批准课时安排",
    toStep: "lesson-division",
  },
  "ppt-outline": {
    actionLabel: "去确认教案",
    dependencyKey: "lesson-plan",
    title: "先确认教案",
    toStep: "lesson-plan",
  },
  "ppt-cover": {
    actionLabel: "去确认逐页设计稿",
    dependencyKey: "ppt-design",
    title: "先确认逐页设计稿",
    toStep: "ppt-design",
  },
  "ppt-design": {
    actionLabel: "去确认页面安排",
    dependencyKey: "ppt-outline",
    title: "先确认页面安排",
    toStep: "ppt-outline",
  },
  "ppt-pages": {
    actionLabel: "去选择封面",
    dependencyKey: "ppt-cover",
    title: "先采用一张封面",
    toStep: "ppt-cover",
  },
  "ppt-export": {
    actionLabel: "去确认 PPT 正文",
    dependencyKey: "ppt-pages",
    title: "先确认整套 PPT",
    toStep: "ppt-pages",
  },
  "master-script": {
    actionLabel: "去选择课堂导入",
    dependencyKey: "intro-options",
    title: "先选择课堂导入方案",
    toStep: "intro-options",
  },
  "rough-storyboard": {
    actionLabel: "去确认母版剧本",
    dependencyKey: "master-script",
    title: "先确认母版剧本",
    toStep: "master-script",
  },
  "video-style": {
    actionLabel: "去确认故事镜头",
    dependencyKey: "rough-storyboard",
    title: "先确认故事镜头",
    toStep: "rough-storyboard",
  },
  "video-assets": {
    actionLabel: "去确认图片资产规划",
    dependencyKey: "video-asset-plan",
    title: "先确认图片资产规划",
    toStep: "video-asset-plan",
  },
  "video-asset-plan": {
    actionLabel: "去确定画面风格",
    dependencyKey: "video-style",
    title: "先确定画面风格",
    toStep: "video-style",
  },
  "fine-storyboard": {
    actionLabel: "去确认镜头图片",
    dependencyKey: "video-assets",
    title: "先确认镜头图片",
    toStep: "video-assets",
  },
  "final-video": {
    actionLabel: "去确认分镜提示词",
    dependencyKey: "fine-storyboard",
    title: "先确认分镜提示词",
    toStep: "fine-storyboard",
  },
};

function nodeStatus(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  nodeKey: string,
) {
  const expectedLessonId = nodeKey === "lesson-division" ? "*" : lessonId;
  return runtime.nodeStates[`${projectId}:${expectedLessonId}:${nodeKey}`]?.status;
}

function requirementSatisfied(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  dependencyKey: string,
) {
  if (dependencyKey === "materials") {
    return hasReadyTextbook(runtime, projectId);
  }
  const status = nodeStatus(runtime, projectId, lessonId, dependencyKey);
  if (status === "stale") return false;
  if (dependencyKey === "lesson-division") {
    if (status !== "approved") return false;
    const approvedLessons = readLessonList(
      runtime.drafts[`project:${projectId}:lessons-approved`]?.value,
    );
    return approvedLessons?.some((lesson) => lesson.id === lessonId) === true;
  }
  if (dependencyKey === "intro-options") {
    if (status !== "approved") return false;
    const draftValue =
      runtime.drafts[`project:${projectId}:lesson:${lessonId}:intro-options`]?.value;
    if (draftValue === undefined) {
      return true;
    }
    const fallbackKey = introOptions[0]?.key ?? "";
    return isPreviewAdopted(readIntroOptionsDraft(draftValue, fallbackKey));
  }

  if (getApprovedDraftValue(runtime, projectId, lessonId, dependencyKey) !== undefined) {
    return true;
  }
  return status === "approved";
}

export function hasReadyTextbook(runtime: MockRuntimeState, projectId: string) {
  return runtime.textbookFiles[projectId]?.some((file) => file.status === "ready") === true;
}

export function getWorkbenchStepBlocker(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  stepKey: string,
) {
  const requirement = stepRequirements[stepKey];
  if (
    !requirement ||
    requirementSatisfied(runtime, projectId, lessonId, requirement.dependencyKey)
  ) {
    return null;
  }
  return requirement;
}

export function getPreviousWorkbenchStepKey(stepKey: string) {
  return stepRequirements[stepKey]?.toStep ?? null;
}

export function getWorkbenchStepStatus(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  stepKey: string,
): WorkflowStatus {
  if (stepKey === "materials") {
    return hasReadyTextbook(runtime, projectId) ? "ready" : "not_ready";
  }
  const nodeKey = stepKey === "ppt-export" ? "ppt-pages" : stepKey;
  const expectedLessonId = nodeKey === "lesson-division" ? "*" : lessonId;
  const explicitStatus = runtime.nodeStates[`${projectId}:${expectedLessonId}:${nodeKey}`]?.status;
  if (nodeKey === "lesson-division" && explicitStatus === "approved") {
    const approvedLessons = readLessonList(
      runtime.drafts[`project:${projectId}:lessons-approved`]?.value,
    );
    if (!approvedLessons?.length) return "review_required";
  }
  if (explicitStatus) return explicitStatus;
  return getWorkbenchStepBlocker(runtime, projectId, lessonId, stepKey) ? "not_ready" : "ready";
}
