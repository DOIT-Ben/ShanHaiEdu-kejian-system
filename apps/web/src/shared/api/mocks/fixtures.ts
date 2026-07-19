import { demoProjectId } from "@/shared/data/mockData";

export const mockNow = "2026-07-17T02:24:00Z";
export const mockProjects = [
  {
    id: demoProjectId,
    title: "认识百分数",
    subject: "primary_math" as const,
    grade: "六年级",
    textbook_edition: "人教版",
    knowledge_point: "百分数的意义与读写",
    status: "active" as const,
    automation_mode: "assisted" as const,
    created_at: "2026-07-12T02:00:00Z",
    updated_at: mockNow,
  },
  {
    id: "01960000-0000-7000-8000-000000000002",
    title: "平行四边形的面积",
    subject: "primary_math" as const,
    grade: "五年级",
    textbook_edition: "苏教版",
    knowledge_point: "转化思想与面积公式",
    status: "active" as const,
    automation_mode: "manual" as const,
    created_at: "2026-07-10T06:00:00Z",
    updated_at: "2026-07-16T08:40:00Z",
  },
  {
    id: "01960000-0000-7000-8000-000000000003",
    title: "圆的认识",
    subject: "primary_math" as const,
    grade: "六年级",
    textbook_edition: "北师大版",
    knowledge_point: "圆心、半径与直径",
    status: "active" as const,
    automation_mode: "automatic" as const,
    created_at: "2026-07-08T03:00:00Z",
    updated_at: "2026-07-15T06:03:00Z",
  },
];

const introCategories = [
  { value: "science", code: "SCI", title: "科普观察" },
  { value: "application", code: "APP", title: "真实任务" },
  { value: "story", code: "STO", title: "故事悬念" },
] as const;

export const mockIntroOptions = introCategories.flatMap((category, categoryIndex) =>
  Array.from({ length: 3 }, (_, optionIndex) => {
    const position = optionIndex + 1;
    return {
      option_key: `INTRO-${category.code}-${String(position).padStart(2, "0")}`,
      category: category.value,
      title: `${category.title} ${String(position)}`,
      independent_concept: "一个脱离课程仍能独立成立、适合小学生理解的观察或任务。",
      hook: "画面在关键变化处提出一个值得继续追问的问题。",
      viewer_value: "即使不知道课程主题，也能理解事件并愿意继续观察。",
      suggested_medium: "video" as const,
      duration_seconds: 45,
      replacement_field_key: null,
      course_anchor: "只补充一个与本课整体和部分关系有关的最小回接。",
      classroom_first_question: "怎样用一个数清楚地描述这一部分占整体的多少？",
      handoff_moment: "问题出现后画面停止，由教师接回课堂。",
      must_not_preteach: ["百分数定义", "完整计算方法"],
      fit_reason: "节奏清楚，课程连接自然，制作成本可控。",
      risks: ["避免提前给出结论"],
      recommendation_score: 96 - categoryIndex * 4 - optionIndex * 6,
      recommendation_reason: "综合课堂节奏、适配度、制作成本和风险得分。",
    };
  }),
);

export const mockEnvelope = <T>(data: T, requestId: string) => ({
  data,
  request_id: requestId,
});
