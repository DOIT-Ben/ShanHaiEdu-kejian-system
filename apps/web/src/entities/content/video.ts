import { z } from "zod";

/**
 * 视频链固定顺序：
 * 母版剧本 → 视觉方向 → 视觉母图 → 粗分镜 → 图片资产 → 细分镜
 * → 镜头提示词 → 视频片段 → 声音与字幕 → 剪辑成片。
 * 图片资产生成必须在粗分镜之后、细分镜之前。
 */

export const masterScriptSceneSchema = z.object({
  scene_id: z.string(),
  scene_no: z.number().int().min(1),
  title: z.string(),
  narration: z.string(),
  visual_idea: z.string().default(""),
  anchor_id: z.string().nullable().default(null),
  duration_seconds: z.number().int().min(1).default(20),
});

export const masterScriptContentSchema = z.object({
  intro_option_id: z.string(),
  intro_option_title: z.string(),
  total_duration_seconds: z.number().int().min(10),
  scenes: z.array(masterScriptSceneSchema),
});

export const visualDirectionContentSchema = z.object({
  style_name: z.string(),
  style_keywords: z.array(z.string()).default([]),
  palette: z.array(z.string()).default([]),
  character_notes: z.string().default(""),
  scene_notes: z.string().default(""),
  reference_asset_ids: z.array(z.string()).default([]),
});

export const masterImageCandidateSchema = z.object({
  candidate_id: z.string(),
  asset_id: z.string(),
  prompt_summary: z.string().default(""),
  selected: z.boolean().default(false),
});

export const masterImageContentSchema = z.object({
  candidates: z.array(masterImageCandidateSchema),
  selected_asset_id: z.string().nullable().default(null),
});

export const roughShotSchema = z.object({
  shot_id: z.string(),
  shot_no: z.number().int().min(1),
  scene_id: z.string(),
  scene_title: z.string().default(""),
  description: z.string(),
  camera: z.string().default(""),
  duration_seconds: z.number().int().min(1).max(60).default(5),
  narration: z.string().default(""),
});

export const roughStoryboardContentSchema = z.object({
  shots: z.array(roughShotSchema),
});

export const imageAssetItemSchema = z.object({
  image_id: z.string(),
  asset_id: z.string().nullable().default(null),
  shot_ids: z.array(z.string()),
  prompt_summary: z.string().default(""),
  based_on_master_image: z.boolean().default(true),
  status: z.enum(["pending", "generating", "completed", "failed"]).default("pending"),
  error_message: z.string().nullable().default(null),
});

export const imageAssetsContentSchema = z.object({
  items: z.array(imageAssetItemSchema),
});

export const fineShotSchema = z.object({
  shot_id: z.string(),
  shot_no: z.number().int().min(1),
  scene_title: z.string().default(""),
  description: z.string(),
  first_frame_asset_id: z.string().nullable().default(null),
  motion_notes: z.string().default(""),
  camera: z.string().default(""),
  dialogue: z.string().default(""),
  subtitle_text: z.string().default(""),
  duration_seconds: z.number().int().min(1).max(60).default(5),
});

export const fineStoryboardContentSchema = z.object({
  shots: z.array(fineShotSchema),
});

export const shotPromptSchema = z.object({
  shot_id: z.string(),
  shot_no: z.number().int().min(1),
  prompt_text: z.string(),
  negative_prompt: z.string().default(""),
  first_frame_asset_id: z.string().nullable().default(null),
  model_hint: z.string().default(""),
});

export const shotPromptsContentSchema = z.object({
  prompts: z.array(shotPromptSchema),
});

export const clipSchema = z.object({
  clip_id: z.string(),
  shot_id: z.string(),
  shot_no: z.number().int().min(1),
  attempt: z.number().int().min(1).default(1),
  status: z.enum(["queued", "generating", "completed", "failed", "approved"]).default("queued"),
  video_asset_id: z.string().nullable().default(null),
  duration_seconds: z.number().int().min(0).default(0),
  error_message: z.string().nullable().default(null),
});

export const clipsContentSchema = z.object({
  clips: z.array(clipSchema),
});

export const subtitleSegmentSchema = z.object({
  start_seconds: z.number().min(0),
  end_seconds: z.number().min(0),
  text: z.string(),
});

export const audioSubtitleContentSchema = z.object({
  voice_name: z.string().default("标准女声"),
  audio_asset_id: z.string().nullable().default(null),
  subtitle_asset_id: z.string().nullable().default(null),
  segments: z.array(subtitleSegmentSchema).default([]),
});

export const finalCutContentSchema = z.object({
  video_asset_id: z.string().nullable().default(null),
  duration_seconds: z.number().min(0).default(0),
  resolution: z.string().default("1920x1080"),
  size_bytes: z.number().int().min(0).default(0),
  included_shot_ids: z.array(z.string()).default([]),
});

export type MasterScriptContent = z.infer<typeof masterScriptContentSchema>;
export type VisualDirectionContent = z.infer<typeof visualDirectionContentSchema>;
export type MasterImageContent = z.infer<typeof masterImageContentSchema>;
export type RoughShot = z.infer<typeof roughShotSchema>;
export type RoughStoryboardContent = z.infer<typeof roughStoryboardContentSchema>;
export type ImageAssetItem = z.infer<typeof imageAssetItemSchema>;
export type ImageAssetsContent = z.infer<typeof imageAssetsContentSchema>;
export type FineShot = z.infer<typeof fineShotSchema>;
export type FineStoryboardContent = z.infer<typeof fineStoryboardContentSchema>;
export type ShotPrompt = z.infer<typeof shotPromptSchema>;
export type ShotPromptsContent = z.infer<typeof shotPromptsContentSchema>;
export type Clip = z.infer<typeof clipSchema>;
export type ClipsContent = z.infer<typeof clipsContentSchema>;
export type AudioSubtitleContent = z.infer<typeof audioSubtitleContentSchema>;
export type FinalCutContent = z.infer<typeof finalCutContentSchema>;
