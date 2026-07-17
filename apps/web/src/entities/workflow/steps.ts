/**
 * 课时工作台左侧流程栏定义（docs/frontend/02_项目与课时工作台.md §2）。
 * 流程栏使用教师行动语言，只负责定位；节点真实状态来自后端 node_runs。
 * 步骤（rail 可点击项）与节点（后端 node_key）解耦：
 * 一个节点可以对应多个步骤（例如教案的「生成」与「修改并确认」）。
 * 新节点通过 stepRegistry 注册，不在页面堆叠类型判断。
 */

export type StepGroupKey =
  | "prepare"
  | "lesson_plan"
  | "intro"
  | "ppt"
  | "video"
  | "delivery";

export interface StepGroup {
  key: StepGroupKey;
  label: string;
}

export const STEP_GROUPS: StepGroup[] = [
  { key: "prepare", label: "准备课程" },
  { key: "lesson_plan", label: "写教案" },
  { key: "intro", label: "选课堂导入" },
  { key: "ppt", label: "做PPT" },
  { key: "video", label: "做导入视频" },
  { key: "delivery", label: "下载成果" },
];

export interface StepDefinition {
  /** URL 中的 stepKey（/work/:stepKey）。 */
  key: string;
  label: string;
  group: StepGroupKey;
  /** 后端 node_key；项目级链接类步骤为 null。 */
  nodeKey: string | null;
  /**
   * link 步骤跳转到项目级页面（查看教材/安排课时/下载成果）；
   * canvas 步骤在工作台中央渲染画布。
   */
  kind: "link" | "canvas";
  /** 同一节点的展示侧重：generate＝准备与生成；review＝修改并确认。 */
  mode?: "generate" | "review";
  /** 所属分支，用于未启用分支的置灰与提示。 */
  branch?: "ppt" | "video" | "intro";
}

export const STEPS: StepDefinition[] = [
  { key: "textbook", label: "查看教材", group: "prepare", nodeKey: null, kind: "link" },
  { key: "lesson-division", label: "安排课时", group: "prepare", nodeKey: null, kind: "link" },
  { key: "lesson-plan", label: "生成教案", group: "lesson_plan", nodeKey: "lesson_plan", kind: "canvas", mode: "generate" },
  { key: "lesson-plan-confirm", label: "修改并确认", group: "lesson_plan", nodeKey: "lesson_plan", kind: "canvas", mode: "review" },
  { key: "intro-options", label: "查看三类九套", group: "intro", nodeKey: "intro_options", kind: "canvas", branch: "intro" },
  { key: "intro-selection", label: "选择一套方案", group: "intro", nodeKey: "intro_selection", kind: "canvas", branch: "intro" },
  { key: "ppt-outline", label: "安排页面", group: "ppt", nodeKey: "ppt_outline", kind: "canvas", branch: "ppt" },
  { key: "ppt-cover", label: "设计封面", group: "ppt", nodeKey: "ppt_cover", kind: "canvas", branch: "ppt" },
  { key: "ppt-body", label: "制作正文", group: "ppt", nodeKey: "ppt_body", kind: "canvas", branch: "ppt" },
  { key: "ppt-export", label: "导出PPT", group: "ppt", nodeKey: "ppt_export", kind: "canvas", branch: "ppt" },
  { key: "video-script", label: "编写母版剧本", group: "video", nodeKey: "video_script", kind: "canvas", branch: "video" },
  { key: "video-storyboard", label: "安排故事镜头", group: "video", nodeKey: "video_storyboard", kind: "canvas", branch: "video" },
  { key: "video-style", label: "确定画面风格", group: "video", nodeKey: "video_style", kind: "canvas", branch: "video" },
  { key: "video-assets", label: "制作镜头图片", group: "video", nodeKey: "video_assets", kind: "canvas", branch: "video" },
  { key: "video-clips", label: "制作视频片段", group: "video", nodeKey: "video_clips", kind: "canvas", branch: "video" },
  { key: "video-compose", label: "合成完整视频", group: "video", nodeKey: "video_compose", kind: "canvas", branch: "video" },
  { key: "download", label: "下载成果", group: "delivery", nodeKey: null, kind: "link" },
];

const stepIndex = new Map(STEPS.map((s) => [s.key, s]));

export function getStep(stepKey: string): StepDefinition | undefined {
  return stepIndex.get(stepKey);
}

export function stepsOfGroup(group: StepGroupKey): StepDefinition[] {
  return STEPS.filter((s) => s.group === group);
}

/** 节点在流程栏中的首选步骤（用于「继续制作」跳转）。 */
export function stepKeyForNode(nodeKey: string, status?: string): string | null {
  const candidates = STEPS.filter((s) => s.nodeKey === nodeKey);
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0].key;
  // 生成/确认双步骤：等待确认时定位到「修改并确认」
  const review = candidates.find((s) => s.mode === "review");
  const generate = candidates.find((s) => s.mode === "generate");
  if (status === "review_required" || status === "approved") return (review ?? candidates[0]).key;
  return (generate ?? candidates[0]).key;
}

/** 视频链路固定顺序（docs/workflows/VIDEO_PRODUCTION.md §2），用于依赖提示。 */
export const VIDEO_NODE_ORDER = [
  "video_script",
  "video_storyboard",
  "video_style",
  "video_assets",
  "video_clips",
  "video_compose",
] as const;
