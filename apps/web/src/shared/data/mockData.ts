import type { LessonSummary, ProjectSummary } from "@/entities/project/model";
import type { ContractWorkflowStatus } from "@/entities/workflow/model";

export const demoProjectId = "01960000-0000-7000-8000-000000000001";
export const demoLessonId = "01960000-0000-7000-8000-000000000101";

export const projects: ProjectSummary[] = [
  {
    id: demoProjectId,
    title: "认识百分数",
    knowledgePoint: "百分数的意义与读写",
    grade: "六年级",
    textbookEdition: "人教版",
    currentLesson: "第 1 课时 · 百分数的意义",
    nextAction: "确认教案中的课堂探究环节",
    progressLabel: "教案待确认",
    updatedAt: "今天 10:24",
  },
  {
    id: "01960000-0000-7000-8000-000000000002",
    title: "平行四边形的面积",
    knowledgePoint: "转化思想与面积公式",
    grade: "五年级",
    textbookEdition: "苏教版",
    currentLesson: "第 2 课时 · 面积公式应用",
    nextAction: "从 3 张备选封面中选择 PPT 封面",
    progressLabel: "封面待选择",
    updatedAt: "昨天 16:40",
  },
  {
    id: "01960000-0000-7000-8000-000000000003",
    title: "圆的认识",
    knowledgePoint: "圆心、半径与直径",
    grade: "六年级",
    textbookEdition: "北师大版",
    currentLesson: "第 1 课时 · 圆的特征",
    nextAction: "查看课堂导入视频生成状态",
    progressLabel: "视频生成中",
    updatedAt: "7 月 15 日",
  },
];

export const lessons: LessonSummary[] = [
  {
    id: demoLessonId,
    title: "第 1 课时 · 百分数的意义",
    scope: "理解百分数表示一个数是另一个数的百分之几，能正确读写百分数。",
    duration: 40,
    planStatus: "review_required",
    introStatus: "approved",
    pptStatus: "not_ready",
    videoStatus: "ready",
  },
  {
    id: "01960000-0000-7000-8000-000000000102",
    title: "第 2 课时 · 百分数与分数、小数",
    scope: "沟通百分数、分数和小数之间的联系，解决简单转换问题。",
    duration: 40,
    planStatus: "draft",
    introStatus: "review_required",
    pptStatus: "disabled",
    videoStatus: "disabled",
  },
];

export const projectSteps: Array<{
  group: string;
  items: Array<{ key: string; label: string; status: ContractWorkflowStatus }>;
}> = [
  {
    group: "准备课程",
    items: [
      { key: "materials", label: "查看教材", status: "approved" },
      { key: "lesson-division", label: "安排课时", status: "approved" },
    ],
  },
  {
    group: "写教案",
    items: [{ key: "lesson-plan", label: "编写并确认教案", status: "review_required" }],
  },
  {
    group: "选课堂导入",
    items: [{ key: "intro-options", label: "选择课堂导入", status: "review_required" }],
  },
  {
    group: "做 PPT",
    items: [
      { key: "ppt-outline", label: "安排页面", status: "not_ready" },
      { key: "ppt-design", label: "逐页设计稿", status: "not_ready" },
      { key: "ppt-cover", label: "设计封面", status: "not_ready" },
      { key: "ppt-pages", label: "制作正文", status: "not_ready" },
      { key: "ppt-export", label: "导出 PPT", status: "not_ready" },
    ],
  },
  {
    group: "做导入视频",
    items: [
      { key: "master-script", label: "编写母版剧本", status: "ready" },
      { key: "rough-storyboard", label: "安排故事镜头", status: "not_ready" },
      { key: "video-style", label: "确定画面风格", status: "not_ready" },
      { key: "video-asset-plan", label: "规划图片资产", status: "not_ready" },
      { key: "video-assets", label: "制作镜头图片", status: "not_ready" },
      { key: "fine-storyboard", label: "设计分镜提示词", status: "not_ready" },
      { key: "final-video", label: "生成课堂导入视频", status: "not_ready" },
    ],
  },
];

export const taskItems = [
  {
    id: "task-1",
    title: "认识百分数 · 教案等待确认",
    detail: "第 1 课时的教案已通过结构与质量检查",
    stage: "等待你确认",
    status: "review_required" as const,
    time: "2 分钟前",
  },
  {
    id: "task-2",
    title: "平行四边形的面积 · PPT 图片",
    detail: "8 张已完成，1 张需要重新制作",
    stage: "部分完成",
    status: "partially_completed" as const,
    time: "12 分钟前",
  },
  {
    id: "task-3",
    title: "圆的认识 · 课堂导入视频",
    detail: "正在根据 6 个已选择关键帧生成画面、旁白和字幕",
    stage: "生成声音与字幕",
    status: "running" as const,
    time: "进行中",
  },
];
