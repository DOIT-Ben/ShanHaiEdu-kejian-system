import type { MockRuntimeState } from "@/shared/api/mocks/runtime";
import {
  createTopicVideoAssets,
  createTopicVideoShots,
} from "@/features/workbench/lib/videoContent";
import {
  createAssetsFromApprovedStory,
  createShotsFromApprovedStory,
  getApprovedFineStoryboard,
  getApprovedVideoStyle,
} from "@/features/workbench/lib/videoWorkflow";

export type ProjectCreationPackageItem = {
  duration?: string;
  id: string;
  prompt: string;
  ratio: "16:9";
  referenceNames?: string[];
  slotKey: string;
  slotLabel: string;
  style: "clay" | "illustration" | "paper";
  title: string;
  type: string;
};

function resolveStyle(runtime: MockRuntimeState, projectId: string, lessonId: string) {
  const selectedId = getApprovedVideoStyle(runtime, projectId, lessonId)?.selectedId;
  if (selectedId === "clay") return { label: "柔和黏土定格", value: "clay" as const };
  if (selectedId === "clean") return { label: "清透实物插画", value: "illustration" as const };
  return { label: "纸艺微缩课堂", value: "paper" as const };
}

export function createProjectVideoShotPackage(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): ProjectCreationPackageItem[] {
  const project = runtime.projects.find((item) => item.id === projectId);
  if (!project) return [];
  const shots =
    createShotsFromApprovedStory(runtime, projectId, lessonId) ??
    createTopicVideoShots(project.knowledge_point);
  const adoptedIds = getApprovedFineStoryboard(runtime, projectId, lessonId)?.adoptedShots ?? [];
  const selectedShots = adoptedIds.length
    ? shots.filter((shot) => adoptedIds.includes(shot.id))
    : shots;
  const style = resolveStyle(runtime, projectId, lessonId);

  return selectedShots.map((shot, index) => ({
    duration: String(shot.duration),
    id: `shot-${String(index + 1)}`,
    prompt: [
      `为小学数学“${project.knowledge_point}”课堂导入制作${shot.id}：${shot.beat}。`,
      `采用${style.label}，运镜为“${shot.movement}”，时长约 ${String(shot.duration)} 秒。`,
      `挂靠${shot.id}的已确认关键帧作为首帧参考，保持人物、场景和教具一致。`,
      "画面清楚、节奏克制，不出现水印、Logo、乱码或无关文字。",
    ].join("\n"),
    ratio: "16:9",
    referenceNames: [`${shot.id}关键帧参考`],
    slotKey: `video.shot.${lessonId}.${String(index + 1)}`,
    slotLabel: `${shot.id}（课堂导入视频分镜）`,
    style: style.value,
    title: `${shot.id} · ${shot.beat}`,
    type: "分镜",
  }));
}

export function createProjectVideoAssetPackage(
  runtime: MockRuntimeState,
  projectId: string,
  lessonId: string,
): ProjectCreationPackageItem[] {
  const project = runtime.projects.find((item) => item.id === projectId);
  if (!project) return [];
  const assets =
    createAssetsFromApprovedStory(runtime, projectId, lessonId) ??
    createTopicVideoAssets(project.knowledge_point);
  const style = resolveStyle(runtime, projectId, lessonId);

  return assets.map((asset) => ({
    id: asset.id,
    prompt: [
      `为小学数学“${project.knowledge_point}”课堂导入视频制作${asset.type}素材：${asset.title}。`,
      `采用${style.label}，画面清晰、克制、适合课堂投屏。`,
      "构图服务于教师讲解，主体明确，保留镜头衔接空间。",
      "不要水印、Logo、乱码；涉及文字或数字时必须准确。",
    ].join("\n"),
    ratio: "16:9",
    slotKey: `video.asset.${lessonId}.${asset.id}`,
    slotLabel: `${asset.title}（视频画面素材）`,
    style: style.value,
    title: asset.title,
    type: asset.type,
  }));
}
