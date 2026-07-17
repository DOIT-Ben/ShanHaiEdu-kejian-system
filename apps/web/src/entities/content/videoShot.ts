import { z } from "zod";

/**
 * 细分镜合同（contracts/video-shot.schema.json）：
 * 一个 shot 一个可见节拍、一个主要运镜、10/15 秒规格、垫图与提示词一一对应。
 */

export const videoShotSchema = z.object({
  shot_id: z.string().regex(/^SHOT-[0-9]{2,}$/),
  scene_id: z.string().min(1),
  position: z.number().int().min(1),
  duration_seconds: z.union([z.literal(10), z.literal(15)]),
  visible_beat: z.string().min(1),
  start_state: z.string().min(1),
  end_state: z.string().min(1),
  camera: z.object({
    framing: z.string(),
    angle: z.string(),
    movement: z.string(),
    start_composition: z.string(),
    end_composition: z.string(),
  }),
  action: z.string().min(1),
  asset_usages: z
    .array(
      z.object({
        image_index: z.number().int().min(1),
        asset_version_id: z.string(),
        semantic_name: z.string().min(1),
        purpose: z.string().min(1),
      }),
    )
    .min(1),
  prompt_text: z.string().min(1),
  narration_text: z.string().optional(),
  dialogue_text: z.string().optional(),
  sound_intent: z.string().optional(),
  continuity_notes: z.string().min(1),
  negative_constraints: z.array(z.string()).optional(),
});

export type VideoShot = z.infer<typeof videoShotSchema>;

/** 垫图标记必须与结构化 asset_usages 一一对应（VIDEO_PRODUCTION.md §7）。 */
export function checkAssetUsageConsistency(shot: VideoShot): string[] {
  const problems: string[] = [];
  const indices = shot.asset_usages.map((u) => u.image_index).sort((a, b) => a - b);
  indices.forEach((value, i) => {
    if (value !== i + 1) {
      problems.push(`垫图序号必须从 1 连续编号，当前为 ${indices.join("、")}。`);
    }
  });
  for (const usage of shot.asset_usages) {
    if (!shot.prompt_text.includes(`[图${usage.image_index}]`)) {
      problems.push(`生成指令中缺少与垫图 ${usage.image_index}（${usage.semantic_name}）对应的 [图${usage.image_index}] 标记。`);
    }
  }
  return [...new Set(problems)];
}

/** 视频四类图片资产（VIDEO_PRODUCTION.md §6）。 */
export const VIDEO_ASSET_KINDS = ["character", "scene", "prop", "creature"] as const;
export type VideoAssetKind = (typeof VIDEO_ASSET_KINDS)[number];

export const VIDEO_ASSET_KIND_LABELS: Record<VideoAssetKind, string> = {
  character: "人物",
  scene: "场景",
  prop: "道具",
  creature: "生物",
};
