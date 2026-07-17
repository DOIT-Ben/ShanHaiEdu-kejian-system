import { z } from "zod";

/**
 * 三类九套导入设计（contracts/intro-option-set.schema.json）。
 */

export const INTRO_CATEGORIES = ["science", "application", "story"] as const;
export type IntroCategory = (typeof INTRO_CATEGORIES)[number];

export const introOptionSchema = z.object({
  option_key: z.string().regex(/^INTRO-(SCI|APP|STO)-[0-9]{2}$/),
  category: z.enum(INTRO_CATEGORIES),
  title: z.string().min(1),
  independent_concept: z.string().min(1),
  hook: z.string().min(1),
  viewer_value: z.string().min(1),
  suggested_medium: z.enum(["video", "image", "physical_object", "question", "performance", "mixed"]),
  duration_seconds: z.number().int().min(10).max(600),
  replacement_field_key: z.string().nullable(),
  course_anchor: z.string().min(1),
  classroom_first_question: z.string().min(1),
  handoff_moment: z.string().min(1),
  must_not_preteach: z.array(z.string().min(1)),
  fit_reason: z.string().min(1),
  risks: z.array(z.string().min(1)),
  recommendation_score: z.number().int().min(1).max(100),
  recommendation_reason: z.string().min(1),
});

export type IntroOption = z.infer<typeof introOptionSchema>;

export const introOptionSetSchema = z.object({
  option_set_id: z.string(),
  lesson_unit_id: z.string(),
  status: z.enum(["draft", "review_required", "approved", "stale"]),
  ideation_context_snapshot_id: z.string(),
  anchoring_context_snapshot_id: z.string(),
  options: z.array(introOptionSchema).length(9),
  created_at: z.string(),
});

export type IntroOptionSet = z.infer<typeof introOptionSetSchema>;

/** 按推荐度排序（选择协议 §5：先展示打分依据）。 */
export function sortByRecommendation(options: IntroOption[]): IntroOption[] {
  return [...options].sort((a, b) => b.recommendation_score - a.recommendation_score);
}

export function groupByCategory(options: IntroOption[]): Record<IntroCategory, IntroOption[]> {
  const grouped: Record<IntroCategory, IntroOption[]> = {
    science: [],
    application: [],
    story: [],
  };
  for (const option of options) grouped[option.category].push(option);
  for (const key of INTRO_CATEGORIES) {
    grouped[key].sort((a, b) => b.recommendation_score - a.recommendation_score);
  }
  return grouped;
}
