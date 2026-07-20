import type { WorkflowStatus } from "@/entities/workflow/model";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import {
  getConfirmedFinalVideoMedia,
  getPlayableFinalVideo,
  type PlayableVideoMedia,
} from "@/features/workbench/lib/videoMedia";
import type { MockRuntimeState } from "@/shared/api/mocks/runtime";

const disabledVideoStatuses = new Set<WorkflowStatus>(["disabled", "skipped"]);

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
  const hasUnconfirmedMedia = candidates.some(
    (candidate) =>
      Boolean(candidate.media) &&
      candidate.node?.status === "approved" &&
      !candidate.confirmedMedia,
  );

  if (confirmed.length === enabled.length) {
    return {
      confirmed,
      detail: `${String(confirmed.length)} 个课时视频可播放`,
      enabledCount: enabled.length,
      status: "approved",
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

  const pendingStatus = enabled.find(({ lesson }) => lesson.videoStatus !== "approved")?.lesson
    .videoStatus;
  return {
    confirmed,
    detail: "关键帧参考已保存，视频尚未生成",
    enabledCount: enabled.length,
    status: pendingStatus ?? "not_ready",
  };
}
