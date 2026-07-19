import type { ScriptScene } from "@/features/workbench/lib/documentMarkdown";
import { getApprovedDraftValue } from "@/features/workbench/lib/approvedDraft";
import type { VideoAsset, VideoShot, VideoStoryBeat } from "@/features/workbench/lib/videoContent";
import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

type ApprovedMasterScript = {
  scenes?: ScriptScene[];
  title?: string;
};

type ApprovedRoughStoryboard = {
  items?: VideoStoryBeat[];
};

type ApprovedFineStoryboard = {
  adoptedShots?: string[];
  candidateByShot?: Record<string, number>;
};

type ApprovedVideoStyle = {
  selectedId?: string;
};

type ApprovedVideoAssets = {
  resultIds?: Record<string, string>;
};

export function getApprovedMasterScript(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  return getApprovedDraftValue<ApprovedMasterScript>(runtime, projectId, lessonId, "master-script");
}

export function getApprovedVideoTitle(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  return getApprovedMasterScript(runtime, projectId, lessonId)?.title?.trim() || "课堂导入视频";
}

export function createStoryBeatsFromApprovedMaster(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): VideoStoryBeat[] | null {
  const scenes = getApprovedMasterScript(runtime, projectId, lessonId)?.scenes;
  if (!Array.isArray(scenes) || scenes.length === 0) return null;
  return scenes.map((scene, index) => ({
    assets: `场景 ${String(index + 1)}、人物动作与关键线索`,
    event: scene.action,
    time: scene.duration,
    title: scene.title,
  }));
}

export function getApprovedStoryBeats(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): VideoStoryBeat[] | null {
  const rough = getApprovedDraftValue<ApprovedRoughStoryboard>(
    runtime,
    projectId,
    lessonId,
    "rough-storyboard",
  );
  return Array.isArray(rough?.items) && rough.items.length > 0 ? rough.items : null;
}

export function createShotsFromApprovedStory(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): VideoShot[] | null {
  const beats = getApprovedStoryBeats(runtime, projectId, lessonId);
  if (!beats) return null;
  const statuses: VideoShot["status"][] = [
    "approved",
    "review_required",
    "partially_completed",
    "ready",
    "not_ready",
  ];
  return beats.map((beat, index) => ({
    beat: beat.event,
    duration: 10,
    id: `镜头 ${String(index + 1)}`,
    movement: index % 2 === 0 ? "固定中景，轻微向前推进" : "从整体平移到局部",
    status: statuses[index % statuses.length] ?? "review_required",
  }));
}

export function createAssetsFromApprovedStory(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): VideoAsset[] | null {
  const beats = getApprovedStoryBeats(runtime, projectId, lessonId);
  if (!beats) return null;
  const first = beats[0];
  const last = beats[beats.length - 1];
  return [
    { id: "character", type: "人物", title: "参与观察与表达的小学生", status: "ready" },
    {
      id: "scene",
      type: "场景",
      title: first?.assets || "故事开场情境",
      status: "ready",
    },
    {
      id: "props",
      type: "教具",
      title: beats
        .map((beat) => beat.assets)
        .slice(0, 2)
        .join("、"),
      status: "needs_generation",
    },
    {
      id: "keyframe",
      type: "镜头关键帧",
      title: last ? `${last.title}定格画面` : "课堂首问定格画面",
      status: "needs_generation",
    },
  ];
}

export function getApprovedFineStoryboard(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  return getApprovedDraftValue<ApprovedFineStoryboard>(
    runtime,
    projectId,
    lessonId,
    "fine-storyboard",
  );
}

export function getApprovedVideoStyle(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  return getApprovedDraftValue<ApprovedVideoStyle>(runtime, projectId, lessonId, "video-style");
}

export function getApprovedVideoAssets(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
) {
  return getApprovedDraftValue<ApprovedVideoAssets>(runtime, projectId, lessonId, "video-assets");
}
