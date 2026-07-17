/**
 * 教师语言映射（docs/frontend/00_产品范围与固定决策.md §4）。
 * 内部概念对教师隐藏；内部标识只在管理员或故障详情中显示。
 */
export const TEACHER_TERMS = {
  creationPackage: "待生成内容",
  creationBatch: "本次创作",
  artifact: "作品",
  prompt: "完整生成指令",
  styleContract: "画面风格",
  nodeRun: "当前步骤",
  reviewRequired: "等待你确认",
  stale: "内容已变化，建议更新",
  provider: "模型服务",
  clip: "已采用片段",
} as const;

/** shot_id → 镜头1、镜头2（教师端不显示内部 SHOT-xx 键）。 */
export function shotDisplayName(position: number): string {
  return `镜头${position}`;
}

/** 页面位置 → 第1页。 */
export function pageDisplayName(position: number): string {
  return `第${position}页`;
}

/** 导入方案类别的教师文案。 */
export const INTRO_CATEGORY_LABELS: Record<string, string> = {
  science: "科普",
  application: "应用",
  story: "故事",
};

export const INTRO_MEDIUM_LABELS: Record<string, string> = {
  video: "视频",
  image: "图片",
  physical_object: "实物",
  question: "提问",
  performance: "表演",
  mixed: "混合",
};
