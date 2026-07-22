import type { MockRuntimeState, MockRuntimeStore } from "@/shared/api/mockClient";
import { mockRuntime, updateMockNodeState } from "@/shared/api/mockClient";
import { readLessonList } from "@/features/workbench/lib/projectLessons";

export type DependentNode = readonly [nodeKey: string, title: string];

const lessonPlanDependents = [
  ["ppt-outline", "安排 PPT 页面"],
  ["ppt-design", "确认逐页设计稿"],
  ["ppt-cover", "选择课件封面"],
  ["ppt-pages", "制作 PPT 正文"],
  ["ppt-export", "检查并导出 PPT"],
] as const;

const pptOutlineDependents = lessonPlanDependents.slice(1);

const pptDesignDependents = pptOutlineDependents.slice(1);

const pptCoverDependents = [["ppt-pages", "制作 PPT 正文"]] as const;

const videoPipelineDependents = [
  ["rough-storyboard", "安排故事镜头"],
  ["video-style", "确定画面风格"],
  ["video-asset-plan", "规划图片资产"],
  ["video-assets", "制作镜头图片"],
  ["fine-storyboard", "设计分镜提示词"],
  ["final-video", "生成课堂导入视频"],
] as const;

const lessonDivisionDependents = [
  ["lesson-plan", "生成教案"],
  ["intro-options", "选择课堂导入"],
  ...lessonPlanDependents,
  ["master-script", "编写母版剧本"],
  ["rough-storyboard", "安排故事镜头"],
  ["video-style", "确定画面风格"],
  ["video-assets", "制作镜头图片"],
  ["fine-storyboard", "选择关键帧参考"],
  ["final-video", "生成课堂导入视频"],
] as const;

/** Mark only existing downstream drafts/nodes stale after a new input version is approved. */
export function markDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  dependentNodes: readonly DependentNode[],
  reason: string,
  store: MockRuntimeStore = mockRuntime,
) {
  for (const [nodeKey, title] of dependentNodes) {
    const stateKey = `${projectId}:${lessonId}:${nodeKey}`;
    const draftKey = `project:${projectId}:lesson:${lessonId}:${nodeKey}`;
    const existing = runtime.nodeStates[stateKey];
    if (!existing && !runtime.drafts[draftKey]) continue;
    updateMockNodeState(
      projectId,
      lessonId,
      nodeKey,
      {
        stale_reason: { summary: reason },
        status: "stale",
        title: existing?.title ?? title,
      },
      store,
    );
    if (nodeKey === "final-video" && existing) {
      for (const task of runtime.tasks) {
        if (
          task.project_id === projectId &&
          task.node_run_id === existing.id &&
          ["queued", "running", "paused"].includes(task.status)
        ) {
          store.updateTask(task.id, { status: "cancel_requested", stage: "等待取消" });
        }
      }
    }
  }
}

export function markLessonPlanDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(
    runtime,
    projectId,
    lessonId,
    lessonPlanDependents,
    "教案已批准新版本，请更新相关课件内容",
    store,
  );
}

export function markPptOutlineDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(
    runtime,
    projectId,
    lessonId,
    pptOutlineDependents,
    "PPT 页面安排已批准新版本，请更新相关课件内容",
    store,
  );
}

export function markPptCoverDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(
    runtime,
    projectId,
    lessonId,
    pptCoverDependents,
    "PPT 封面已批准新版本，请更新课件正文",
    store,
  );
}

export function markPptDesignDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markDependentsStale(
    runtime,
    projectId,
    lessonId,
    pptDesignDependents,
    "PPT 逐页设计稿已批准新版本，请更新封面和正文",
    store,
  );
}

function markVideoDependentsStaleFrom(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  startIndex: number,
  reason: string,
  store: MockRuntimeStore,
) {
  markDependentsStale(
    runtime,
    projectId,
    lessonId,
    videoPipelineDependents.slice(startIndex),
    reason,
    store,
  );
}

export function markMasterScriptDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    0,
    "母版剧本已批准新版本，请更新后续视频内容",
    store,
  );
}

export function markRoughStoryboardDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    1,
    "故事镜头已批准新版本，请更新后续视频内容",
    store,
  );
}

export function markVideoStyleDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    2,
    "画面风格已批准新版本，请更新后续视频内容",
    store,
  );
}

export function markVideoAssetPlanDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    3,
    "图片资产规划已批准新版本，请重新制作镜头图片",
    store,
  );
}

export function markVideoAssetsDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    4,
    "镜头图片已批准新版本，请更新关键帧参考并重新生成视频",
    store,
  );
}

export function markFineStoryboardDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  markVideoDependentsStaleFrom(
    runtime,
    projectId,
    lessonId,
    5,
    "关键帧参考已批准新版本，请重新生成课堂导入视频",
    store,
  );
}

export function markLessonDivisionDependentsStale(
  runtime: MockRuntimeState,
  projectId: string,
  store: MockRuntimeStore = mockRuntime,
) {
  const currentLessons =
    readLessonList(runtime.drafts[`project:${projectId}:lessons`]?.value) ?? [];
  const approvedLessons =
    readLessonList(runtime.drafts[`project:${projectId}:lessons-approved`]?.value) ?? [];
  const lessonIds = new Set([...currentLessons, ...approvedLessons].map((lesson) => lesson.id));
  markLessonDivisionDependentsStaleForLessons(runtime, projectId, lessonIds, store);
}

export function markLessonDivisionDependentsStaleForLessons(
  runtime: MockRuntimeState,
  projectId: string,
  lessonIds: Iterable<string>,
  store: MockRuntimeStore = mockRuntime,
) {
  for (const lessonId of new Set(lessonIds)) {
    if (!lessonId) continue;
    markDependentsStale(
      runtime,
      projectId,
      lessonId,
      lessonDivisionDependents,
      "课时安排已批准新版本，请更新相关课堂内容",
      store,
    );
  }
}
