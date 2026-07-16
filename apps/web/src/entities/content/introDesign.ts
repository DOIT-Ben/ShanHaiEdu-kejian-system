import { z } from "zod";

/**
 * 导入设计「三类九套」（intro_design 产物 content）。
 * 三个创意类别 × 每类三套方案；创意独立生成，锚点负责连接课程。
 */
export const INTRO_CATEGORIES = [
  { key: "science", name: "科普向" },
  { key: "application", name: "应用向" },
  { key: "story", name: "故事向" },
] as const;

export type IntroCategoryKey = (typeof INTRO_CATEGORIES)[number]["key"];

export const introAnchorSchema = z.object({
  anchor_id: z.string(),
  description: z.string(),
  knowledge_point: z.string(),
  status: z.enum(["proposed", "confirmed", "failed"]).default("proposed"),
});

export const introOptionSchema = z.object({
  option_id: z.string(),
  option_no: z.number().int().min(1).max(3),
  title: z.string(),
  summary: z.string(),
  narrative: z.string().default(""),
  style_hint: z.string().default(""),
  duration_seconds: z.number().int().min(10).max(600).default(90),
  anchors: z.array(introAnchorSchema).default([]),
  status: z
    .enum(["draft", "needs_review", "approved", "rejected", "revision_required"])
    .default("needs_review"),
  creative_locked: z.boolean().default(false),
});

export const introCategorySchema = z.object({
  category_key: z.enum(["science", "application", "story"]),
  category_name: z.string(),
  options: z.array(introOptionSchema),
});

export const introDesignContentSchema = z.object({
  categories: z.array(introCategorySchema),
  selected_option_id: z.string().nullable().default(null),
});

export type IntroAnchor = z.infer<typeof introAnchorSchema>;
export type IntroOption = z.infer<typeof introOptionSchema>;
export type IntroCategory = z.infer<typeof introCategorySchema>;
export type IntroDesignContent = z.infer<typeof introDesignContentSchema>;
