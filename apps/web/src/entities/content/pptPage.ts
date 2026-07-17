import { z } from "zod";

/**
 * PPT 页级四层合同（contracts/ppt-page-spec.schema.json）：
 * canvas（封面 cover_art / 正文 solid_white #FFFFFF）、
 * visual（图片主视觉）、content（可编辑文字与数学图形）、layout。
 */

export const PPT_PAGE_TYPES = [
  "cover",
  "introduction",
  "concept",
  "exploration",
  "example",
  "practice",
  "discussion",
  "summary",
  "other",
] as const;

export const PPT_PAGE_TYPE_LABELS: Record<string, string> = {
  cover: "封面",
  introduction: "导入",
  concept: "概念建构",
  exploration: "探究",
  example: "例题",
  practice: "练习",
  discussion: "辨析",
  summary: "总结",
  other: "其他",
};

export const editableTextBlockSchema = z.object({
  block_key: z.string(),
  role: z.enum(["title", "body", "question", "label", "answer", "note"]),
  text: z.string(),
  layout: z.record(z.string(), z.unknown()),
});

export type EditableTextBlock = z.infer<typeof editableTextBlockSchema>;

export const TEXT_ROLE_LABELS: Record<EditableTextBlock["role"], string> = {
  title: "标题",
  body: "正文",
  question: "问题",
  label: "标注",
  answer: "答案",
  note: "备注",
};

export const editableMathShapeSchema = z.object({
  shape_key: z.string(),
  shape_type: z.enum([
    "formula",
    "line_segment",
    "hundred_grid",
    "ratio_bar",
    "progress_bar",
    "arrow",
    "chart",
    "table",
    "custom",
  ]),
  data: z.record(z.string(), z.unknown()),
  layout: z.record(z.string(), z.unknown()),
});

export type EditableMathShape = z.infer<typeof editableMathShapeSchema>;

export const MATH_SHAPE_LABELS: Record<EditableMathShape["shape_type"], string> = {
  formula: "公式",
  line_segment: "线段图",
  hundred_grid: "百格图",
  ratio_bar: "比例条",
  progress_bar: "进度条",
  arrow: "箭头",
  chart: "图表",
  table: "表格",
  custom: "自定义图形",
};

export const pptPageSpecSchema = z.object({
  page_key: z.string().regex(/^PAGE-[0-9]{2,}$/),
  position: z.number().int().min(1),
  page_type: z.enum(PPT_PAGE_TYPES),
  teaching_task: z.string().min(1),
  source_refs: z.array(z.string().min(1)).min(1),
  student_focus: z.string().min(1),
  canvas: z.object({
    aspect_ratio: z.literal("16:9"),
    background_mode: z.enum(["cover_art", "solid_white"]),
    background_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/).optional(),
    safe_area: z.record(z.string(), z.unknown()),
  }),
  visual: z.object({
    visual_decision: z.enum([
      "quantity_relation",
      "whole_part",
      "comparison",
      "transformation",
      "unit_one",
      "change",
      "operation",
      "life_application",
      "other",
    ]),
    image_strategy: z.enum(["textbook_reconstruction", "original_asset", "mixed"]),
    main_visual_description: z.string().min(1),
    asset_requirements: z
      .array(
        z.object({
          requirement_key: z.string().min(1),
          role: z.enum(["main_visual", "supporting_visual", "decorative"]),
          prompt: z.string().min(1),
          negative_prompt: z.string(),
          target_slot_key: z.string().min(1),
        }),
      )
      .min(1),
  }),
  editable_text_blocks: z.array(editableTextBlockSchema),
  editable_math_shapes: z.array(editableMathShapeSchema),
  layout_spec: z.record(z.string(), z.unknown()),
  interaction_spec: z.record(z.string(), z.unknown()),
  speaker_notes: z.string().optional(),
  validation_rules: z.array(z.record(z.string(), z.unknown())).optional(),
});

export type PptPageSpec = z.infer<typeof pptPageSpecSchema>;

/** 正文页硬约束：solid_white + #FFFFFF（PPT_PRODUCTION.md §4）。 */
export function validatePageCanvas(spec: PptPageSpec): string | null {
  if (spec.page_type === "cover") {
    return spec.canvas.background_mode === "cover_art"
      ? null
      : "封面页必须使用主视觉画布（cover_art）。";
  }
  if (spec.canvas.background_mode !== "solid_white") {
    return "正文页背景必须为纯白。";
  }
  if (spec.canvas.background_color !== "#FFFFFF") {
    return "正文页背景色必须为 #FFFFFF。";
  }
  return null;
}
