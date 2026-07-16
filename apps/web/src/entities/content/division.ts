import { z } from "zod";

/** 课时划分（lesson_division 产物 content）。 */
export const divisionLessonSchema = z.object({
  lesson_key: z.string(),
  title: z.string(),
  lesson_type: z.enum(["new_knowledge", "practice", "review", "assessment"]).default("new_knowledge"),
  duration_minutes: z.number().int().min(10).max(120).default(40),
  knowledge_points: z.array(z.string()).default([]),
  textbook_pages: z.string().default(""),
  objectives: z.string().default(""),
});

export const divisionContentSchema = z.object({
  lessons: z.array(divisionLessonSchema),
  rationale: z.string().optional(),
});

export type DivisionLesson = z.infer<typeof divisionLessonSchema>;
export type DivisionContent = z.infer<typeof divisionContentSchema>;

export const lessonTypeLabels: Record<DivisionLesson["lesson_type"], string> = {
  new_knowledge: "新授课",
  practice: "练习课",
  review: "复习课",
  assessment: "测评课",
};
