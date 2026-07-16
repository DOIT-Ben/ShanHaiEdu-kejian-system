import { z } from "zod";

/** 教材证据（textbook_evidence 产物 content）。 */
export const evidenceBlockSchema = z.object({
  type: z.enum(["heading", "paragraph", "example", "exercise", "figure", "formula"]),
  text: z.string(),
  confidence: z.number().min(0).max(1).optional(),
});

export const evidencePageSchema = z.object({
  page_number: z.number().int().min(1),
  title: z.string().optional(),
  ocr_text: z.string(),
  blocks: z.array(evidenceBlockSchema).default([]),
  low_confidence: z.boolean().default(false),
});

export const textbookEvidenceContentSchema = z.object({
  source_file_name: z.string().optional(),
  page_count: z.number().int().min(0),
  pages: z.array(evidencePageSchema),
  summary: z.string().optional(),
});

export type EvidencePage = z.infer<typeof evidencePageSchema>;
export type TextbookEvidenceContent = z.infer<typeof textbookEvidenceContentSchema>;
