import { z } from "zod";

/**
 * 十二部分结构化教案（lesson_plan 产物 content）。
 * 部分顺序与标题固定；「教学过程」为结构化环节列表，其余为长文本。
 */
export const LESSON_PLAN_SECTIONS = [
  { key: "teaching_objectives", title: "教学目标", kind: "text" },
  { key: "core_competencies", title: "核心素养指向", kind: "text" },
  { key: "learner_analysis", title: "学情分析", kind: "text" },
  { key: "key_points", title: "教学重点", kind: "text" },
  { key: "difficult_points", title: "教学难点", kind: "text" },
  { key: "preparation", title: "教学准备", kind: "text" },
  { key: "intro_hook", title: "导入环节", kind: "text" },
  { key: "teaching_process", title: "教学过程", kind: "process" },
  { key: "board_design", title: "板书设计", kind: "text" },
  { key: "exercise_design", title: "练习设计", kind: "text" },
  { key: "homework_design", title: "作业设计", kind: "text" },
  { key: "reflection", title: "教学反思", kind: "text" },
] as const;

export type LessonPlanSectionKey = (typeof LESSON_PLAN_SECTIONS)[number]["key"];

export const processStageSchema = z.object({
  stage_id: z.string(),
  stage_title: z.string(),
  minutes: z.number().int().min(1).max(60),
  teacher_activity: z.string(),
  student_activity: z.string(),
  design_intent: z.string().default(""),
});

export const lessonPlanSectionSchema = z.object({
  key: z.string(),
  title: z.string(),
  kind: z.enum(["text", "process"]),
  body: z.string().default(""),
  stages: z.array(processStageSchema).default([]),
});

export const lessonPlanContentSchema = z.object({
  lesson_title: z.string(),
  sections: z.array(lessonPlanSectionSchema).length(LESSON_PLAN_SECTIONS.length),
});

export type ProcessStage = z.infer<typeof processStageSchema>;
export type LessonPlanSection = z.infer<typeof lessonPlanSectionSchema>;
export type LessonPlanContent = z.infer<typeof lessonPlanContentSchema>;
