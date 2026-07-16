import { z } from "zod";

/** PPT 链：大纲 → 页面脚本 → 配图 → 预览 → 导出。 */

export const pptOutlineSectionSchema = z.object({
  section_id: z.string(),
  title: z.string(),
  page_titles: z.array(z.string()),
});

export const pptOutlineContentSchema = z.object({
  lesson_title: z.string(),
  sections: z.array(pptOutlineSectionSchema),
  estimated_page_count: z.number().int().min(1),
});

export const pptBlockSchema = z.object({
  block_id: z.string(),
  type: z.enum(["heading", "text", "bullets", "image", "formula", "example", "interaction"]),
  text: z.string().default(""),
  items: z.array(z.string()).default([]),
  asset_id: z.string().nullable().default(null),
});

export const pptPageSchema = z.object({
  page_id: z.string(),
  page_no: z.number().int().min(1),
  title: z.string(),
  /** 封面为设计封面；正文页固定纯白底。 */
  layout: z.enum(["cover", "section", "content", "example", "exercise", "summary"]),
  blocks: z.array(pptBlockSchema).default([]),
  speaker_notes: z.string().default(""),
  image_asset_ids: z.array(z.string()).default([]),
  status: z
    .enum(["draft", "needs_review", "approved", "revision_required"])
    .default("needs_review"),
});

export const pptPagesContentSchema = z.object({
  lesson_title: z.string(),
  theme: z.object({
    cover_style: z.literal("designed"),
    body_style: z.literal("pure_white"),
    accent_color: z.string().default("#2854E8"),
  }),
  pages: z.array(pptPageSchema),
});

export const pptExportContentSchema = z.object({
  file_object_id: z.string().nullable().default(null),
  page_count: z.number().int().min(0).default(0),
  exported_at: z.string().nullable().default(null),
  warnings: z.array(z.string()).default([]),
});

export type PptOutlineContent = z.infer<typeof pptOutlineContentSchema>;
export type PptBlock = z.infer<typeof pptBlockSchema>;
export type PptPage = z.infer<typeof pptPageSchema>;
export type PptPagesContent = z.infer<typeof pptPagesContentSchema>;
export type PptExportContent = z.infer<typeof pptExportContentSchema>;

export const pptLayoutLabels: Record<PptPage["layout"], string> = {
  cover: "封面",
  section: "章节页",
  content: "内容页",
  example: "例题页",
  exercise: "练习页",
  summary: "小结页",
};
