import type { Asset, ValidationResult } from "@/shared/api/types";
import { getDb, minutesAgo, nextId, type LessonState, type MockDb, type ProjectState } from "./db";
import { makeImageFileObject, makeFileObject } from "./fixtures/files";
import {
  buildAudioSubtitleContent,
  buildClipsContent,
  buildFinalCutContent,
  buildFineStoryboardContent,
  buildImageAssetsContent,
  buildIntroDesignContent,
  buildLessonPlanContent,
  buildMasterImageContent,
  buildMasterScriptContent,
  buildPptOutlineContent,
  buildPptPagesContent,
  buildRoughStoryboardContent,
  buildShotPromptsContent,
  buildVisualDirectionContent,
  ROUGH_SHOTS,
} from "./fixtures/content";
import type { ImageAssetsContent, IntroDesignContent, ShotPromptsContent } from "@/entities/content";

export function registerGeneratedAsset(input: {
  projectId: string;
  lessonId: string | null;
  assetType: "image" | "video" | "audio" | "subtitle" | "document";
  name: string;
  sourceNodeKey: string;
  hueSeed?: number;
  fileName?: string;
  mimeType?: string;
  sizeBytes?: number;
}): { assetId: string; fileObjectId: string } {
  const db = getDb();
  const assetId = nextId(db, "asset");
  const file =
    input.assetType === "image"
      ? makeImageFileObject(input.name, input.hueSeed ?? 5, "生成资产")
      : makeFileObject({
          fileName: input.fileName ?? `${input.name}.bin`,
          mimeType: input.mimeType ?? "application/octet-stream",
          sizeBytes: input.sizeBytes ?? 2_000_000,
        });
  const asset: Asset = {
    asset_id: assetId,
    asset_type: input.assetType,
    name: input.name,
    status: "needs_review",
    current_version_id: `${assetId}_v1`,
    current_version_number: 1,
    thumbnail_url: input.assetType === "image" ? file.preview_url : null,
    source_node_key: input.sourceNodeKey,
    source_model_name: input.assetType === "image" ? "教学插画·标准" : input.assetType === "video" ? "教学视频·标准" : input.assetType === "audio" ? "旁白配音·标准" : null,
    lesson_id: input.lessonId,
    usage_count: 0,
    created_at: minutesAgo(0),
  };
  db.assets.set(assetId, {
    projectId: input.projectId,
    asset,
    versions: [
      { asset_version_id: `${assetId}_v1`, version_number: 1, status: "needs_review", file_object: file, source_model_name: asset.source_model_name, created_at: minutesAgo(0) },
    ],
    usage: [],
  });
  return { assetId, fileObjectId: file.file_object_id };
}

function revisionNote(instruction: string | null): string {
  return instruction ? `（已按修改意见调整：${instruction}）` : "";
}

interface GenerateInput {
  project: ProjectState;
  lessonState: LessonState;
  nodeKey: string;
  revisionInstruction: string | null;
}

interface GeneratedResult {
  content: Record<string, unknown>;
  validation?: ValidationResult[];
}

/** 节点运行完成时的内容产出（确定性 Mock 生成）。 */
export function generateNodeContent(db: MockDb, input: GenerateInput): GeneratedResult {
  const { project, lessonState, nodeKey, revisionInstruction } = input;
  const projectId = project.project.project_id;
  const lessonId = lessonState.lesson.lesson_id;
  const lessonTitle = lessonState.lesson.title;
  const note = revisionNote(revisionInstruction);

  switch (nodeKey) {
    case "lesson_plan": {
      const content = buildLessonPlanContent(lessonTitle, revisionInstruction ? 2 : 1);
      if (note) content.sections[0].body += `\n${note}`;
      return {
        content: content as unknown as Record<string, unknown>,
        validation: [
          { rule_id: "sections_complete", severity: "error", passed: true, message: "十二部分结构完整" },
          { rule_id: "duration_sum", severity: "info", passed: true, message: "教学过程环节时长合计 40 分钟" },
        ],
      };
    }
    case "intro_design": {
      const content = buildIntroDesignContent({ anchorFailed: db.flags.anchorFailed });
      if (note) content.categories[0].options[0].summary += note;
      return {
        content: content as unknown as Record<string, unknown>,
        validation: db.flags.anchorFailed
          ? [{ rule_id: "anchors_confirmed", severity: "error", passed: false, message: "故事向方案课程锚点未通过校验", action: "锁定创意重出锚点" }]
          : [{ rule_id: "anchors_confirmed", severity: "error", passed: true, message: "九套方案课程锚点全部确认" }],
      };
    }
    case "ppt_outline": {
      const content = buildPptOutlineContent(lessonTitle);
      return { content: content as unknown as Record<string, unknown> };
    }
    case "ppt_pages": {
      const content = buildPptPagesContent(lessonTitle);
      if (note) content.pages[0].speaker_notes += note;
      return { content: content as unknown as Record<string, unknown> };
    }
    case "ppt_assets": {
      const assetIds = [1, 2, 3].map((i) =>
        registerGeneratedAsset({ projectId, lessonId, assetType: "image", name: `教学插图候选${i}`, sourceNodeKey: "ppt_assets", hueSeed: 50 + i }).assetId,
      );
      return { content: { generated_asset_ids: assetIds } };
    }
    case "ppt_export": {
      const file = makeFileObject({ fileName: `${lessonTitle}.pptx`, mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation", sizeBytes: 8_400_000 });
      return { content: { file_object_id: file.file_object_id, page_count: 14, exported_at: minutesAgo(0), warnings: [] } };
    }
    case "video_master_script": {
      const intro = lessonState.nodes.get("intro_design")?.artifactVersions.find((v) => v.status === "approved");
      const introContent = intro?.content as IntroDesignContent | undefined;
      const selected = introContent?.categories.flatMap((c) => c.options).find((o) => o.option_id === introContent?.selected_option_id);
      const content = buildMasterScriptContent(selected?.title ?? "分月饼");
      if (note) content.scenes[0].narration += note;
      return { content: content as unknown as Record<string, unknown> };
    }
    case "video_visual_direction":
      return { content: buildVisualDirectionContent() as unknown as Record<string, unknown> };
    case "video_master_image": {
      const candidates = [1, 2, 3].map((i) => {
        const { assetId } = registerGeneratedAsset({ projectId, lessonId, assetType: "image", name: `视觉母图候选${i}`, sourceNodeKey: "video_master_image", hueSeed: 60 + i * 4 });
        return { candidateId: `cand_gen_${i}`, assetId, summary: i === 1 ? "庭院月夜全景" : i === 2 ? "餐桌温馨特写" : "月光下的分月饼" };
      });
      return { content: buildMasterImageContent(candidates, null) as unknown as Record<string, unknown> };
    }
    case "video_rough_storyboard":
      return { content: buildRoughStoryboardContent() as unknown as Record<string, unknown> };
    case "video_image_assets": {
      const items = ROUGH_SHOTS.map((shot) => {
        const failed = db.flags.imagePartialFail && shot.shotNo === 7;
        if (failed) {
          return { imageId: `img_shot_${shot.shotNo}`, assetId: null, shotIds: [`shot_${shot.shotNo}`], summary: shot.description, failed: true };
        }
        const { assetId } = registerGeneratedAsset({ projectId, lessonId, assetType: "image", name: `镜头${shot.shotNo}首帧`, sourceNodeKey: "video_image_assets", hueSeed: 70 + shot.shotNo });
        return { imageId: `img_shot_${shot.shotNo}`, assetId, shotIds: [`shot_${shot.shotNo}`], summary: shot.description };
      });
      return {
        content: buildImageAssetsContent(items) as unknown as Record<string, unknown>,
        validation: db.flags.imagePartialFail
          ? [{ rule_id: "all_frames_ready", severity: "error", passed: false, message: "镜头 7 首帧生成失败，可单独重试", action: "重试失败镜头" }]
          : [],
      };
    }
    case "video_fine_storyboard": {
      const imageArtifact = lessonState.nodes.get("video_image_assets")?.artifactVersions[0];
      const imageContent = imageArtifact?.content as ImageAssetsContent | undefined;
      const frames: Record<string, string | null> = {};
      for (const item of imageContent?.items ?? []) {
        for (const shotId of item.shot_ids) frames[shotId] = item.asset_id;
      }
      return { content: buildFineStoryboardContent(frames) as unknown as Record<string, unknown> };
    }
    case "video_shot_prompts": {
      const fine = lessonState.nodes.get("video_fine_storyboard")?.artifactVersions[0];
      const fineContent = fine?.content as { shots?: Array<{ shot_id: string; first_frame_asset_id: string | null }> } | undefined;
      const frames: Record<string, string | null> = {};
      for (const shot of fineContent?.shots ?? []) frames[shot.shot_id] = shot.first_frame_asset_id;
      return { content: buildShotPromptsContent(frames) as unknown as Record<string, unknown> };
    }
    case "video_clips": {
      const prompts = lessonState.nodes.get("video_shot_prompts")?.artifactVersions[0]?.content as ShotPromptsContent | undefined;
      const clips = (prompts?.prompts ?? ROUGH_SHOTS.map((s) => ({ shot_id: `shot_${s.shotNo}`, shot_no: s.shotNo }))).map((p) => {
        const shotNo = "shot_no" in p ? p.shot_no : 0;
        const failed = db.flags.clipPartialFail && shotNo === 4;
        if (failed) {
          return { clipId: `clip_${shotNo}_gen`, shotId: p.shot_id, shotNo, status: "failed" as const, error: db.flags.paidFallbackConfirm ? "潮汐视频云连续超时；可切换备用服务重试（已产生费用，切换将再次计费，需确认）。" : "视频生成超时，可重试该镜头。" };
        }
        const { assetId } = registerGeneratedAsset({ projectId, lessonId, assetType: "video", name: `镜头${shotNo}片段`, sourceNodeKey: "video_clips", fileName: `clip_shot_${shotNo}.mp4`, mimeType: "video/mp4", sizeBytes: 6_000_000 });
        return { clipId: `clip_${shotNo}_gen`, shotId: p.shot_id, shotNo, status: "completed" as const, assetId, duration: ROUGH_SHOTS.find((s) => s.shotNo === shotNo)?.duration ?? 8 };
      });
      return {
        content: buildClipsContent(clips) as unknown as Record<string, unknown>,
        validation: db.flags.clipPartialFail
          ? [{ rule_id: "all_clips_ready", severity: "error", passed: false, message: "镜头 4 片段生成失败（部分成功）", action: "重试失败镜头" }]
          : [],
      };
    }
    case "video_audio_subtitle": {
      const audio = registerGeneratedAsset({ projectId, lessonId, assetType: "audio", name: "旁白配音轨", sourceNodeKey: "video_audio_subtitle", fileName: "narration.mp3", mimeType: "audio/mpeg", sizeBytes: 2_200_000 });
      const srt = registerGeneratedAsset({ projectId, lessonId, assetType: "subtitle", name: "字幕文件", sourceNodeKey: "video_audio_subtitle", fileName: "subtitles.srt", mimeType: "application/x-subrip", sizeBytes: 4_200 });
      return { content: buildAudioSubtitleContent(audio.assetId, srt.assetId) as unknown as Record<string, unknown> };
    }
    case "video_final_cut": {
      const video = registerGeneratedAsset({ projectId, lessonId, assetType: "video", name: "导入视频成片", sourceNodeKey: "video_final_cut", fileName: `${lessonTitle}_导入视频.mp4`, mimeType: "video/mp4", sizeBytes: 48_500_000 });
      return { content: buildFinalCutContent(video.assetId) as unknown as Record<string, unknown> };
    }
    default:
      return { content: { note: `节点 ${nodeKey} 生成完成${note}` } };
  }
}
