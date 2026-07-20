import type { WorkflowStatus } from "@/entities/workflow/model";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import {
  getConfirmedFinalVideoMedia,
  getPlayableFinalVideo,
  type PlayableVideoMedia,
} from "@/features/workbench/lib/videoMedia";
import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

const disabledVideoStatuses = new Set<WorkflowStatus>(["disabled", "skipped"]);
const unresolvedStatusPriority: readonly WorkflowStatus[] = [
  "failed",
  "stale",
  "cancel_requested",
  "paused",
  "cancelled",
  "unknown",
  "review_required",
  "partially_completed",
  "running",
  "queued",
  "ready",
  "draft",
  "not_ready",
  "disabled",
  "skipped",
  "approved",
];

const unresolvedStatusDetail: Partial<Record<WorkflowStatus, string>> = {
  cancel_requested: "有课时视频正在取消",
  cancelled: "有课时视频已取消",
  failed: "有课时视频需要重新处理",
  paused: "有课时视频已暂停",
  running: "有课时视频正在制作",
  stale: "有课时视频需要更新",
  unknown: "有课时视频状态需要处理",
};

export type ConfirmedProjectVideo = {
  lessonId: string;
  lessonLabel: string;
  lessonTitle: string;
  media: PlayableVideoMedia;
  revision: number;
};

export type ProjectVideoSummary = {
  confirmed: ConfirmedProjectVideo[];
  detail: string;
  enabledCount: number;
  status: WorkflowStatus;
};

export function getProjectVideoSummary(
  runtime: MockRuntimeState,
  projectId: string,
): ProjectVideoSummary {
  const lessons = getApprovedProjectLessons(runtime, projectId);
  if (lessons.length === 0) {
    return {
      confirmed: [],
      detail: "课时安排完成后显示视频成果",
      enabledCount: 0,
      status: "not_ready",
    };
  }

  const enabled = lessons
    .map((lesson, index) => ({ index, lesson }))
    .filter(({ lesson }) => !disabledVideoStatuses.has(lesson.videoStatus));
  if (enabled.length === 0) {
    return {
      confirmed: [],
      detail: "本项目未启用课堂导入视频",
      enabledCount: 0,
      status: "disabled",
    };
  }

  const candidates = enabled.map(({ index, lesson }) => {
    const media = getPlayableFinalVideo(runtime, projectId, lesson.id);
    const node = runtime.nodeStates[`${projectId}:${lesson.id}:final-video`];
    const confirmedMedia = getConfirmedFinalVideoMedia(runtime, projectId, lesson.id);
    return { confirmedMedia, index, lesson, media, node };
  });
  const confirmed = candidates.flatMap<ConfirmedProjectVideo>((candidate) =>
    candidate.confirmedMedia && candidate.node
      ? [
          {
            lessonId: candidate.lesson.id,
            lessonLabel: `第 ${String(candidate.index + 1)} 课时`,
            lessonTitle: candidate.lesson.title,
            media: candidate.confirmedMedia,
            revision: candidate.node.revision,
          },
        ]
      : [],
  );
  const unresolvedStatuses = candidates.flatMap<WorkflowStatus>((candidate) => {
    if (candidate.confirmedMedia) return [];
    if (candidate.media && candidate.node?.status === "approved") return ["review_required"];
    return [candidate.node?.status ?? candidate.lesson.videoStatus];
  });
  const unresolvedStatus =
    unresolvedStatusPriority.find((status) => unresolvedStatuses.includes(status)) ?? "not_ready";
  const hasUnconfirmedMedia = candidates.some(
    (candidate) => candidate.media && !candidate.confirmedMedia,
  );

  if (confirmed.length === enabled.length) {
    return {
      confirmed,
      detail: `${String(confirmed.length)} 个课时视频可播放`,
      enabledCount: enabled.length,
      status: "approved",
    };
  }
  if (unresolvedStatusDetail[unresolvedStatus]) {
    return {
      confirmed,
      detail: unresolvedStatusDetail[unresolvedStatus] ?? "有课时视频需要处理",
      enabledCount: enabled.length,
      status: unresolvedStatus,
    };
  }
  if (confirmed.length > 0) {
    return {
      confirmed,
      detail: `${String(confirmed.length)}/${String(enabled.length)} 个课时视频可播放`,
      enabledCount: enabled.length,
      status: "partially_completed",
    };
  }
  if (hasUnconfirmedMedia) {
    return {
      confirmed,
      detail: "视频文件等待确认",
      enabledCount: enabled.length,
      status: "review_required",
    };
  }

  return {
    confirmed,
    detail: "关键帧参考已保存，视频尚未生成",
    enabledCount: enabled.length,
    status: unresolvedStatus,
  };
}
