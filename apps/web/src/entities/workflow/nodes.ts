/**
 * 课时级工作流节点图（教师工作台唯一节点来源）。
 * 与 Mock 的 workflow 定义、节点渲染器注册表共用。
 * 视频链顺序固定，图片资产生成位于粗分镜之后、细分镜之前，不得调整。
 */
export interface WorkflowNodeDef {
  key: string;
  title: string;
  group: string;
  rendererKey: string;
  /** 模型能力；null 表示无模型调用（纯人工/系统节点）。 */
  capability: string | null;
  dependsOn: string[];
  skippable: boolean;
  description: string;
}

export const NODE_GROUPS = ["教案", "导入设计", "PPT", "视频", "交付"] as const;

export const LESSON_NODES: WorkflowNodeDef[] = [
  {
    key: "lesson_plan",
    title: "十二部分教案",
    group: "教案",
    rendererKey: "lesson-plan",
    capability: "text_generation",
    dependsOn: [],
    skippable: false,
    description:
      "基于教材证据和课时边界生成十二部分结构化教案。你可以整体生成，也可以对单个部分提出修改意见，批准后进入下游制作。",
  },
  {
    key: "intro_design",
    title: "导入设计（三类九套）",
    group: "导入设计",
    rendererKey: "intro-design",
    capability: "text_generation",
    dependsOn: [],
    skippable: true,
    description:
      "独立生成科普、应用、故事三类各三套导入创意，创意不从教案推导；每套方案带课程锚点，锚点负责连接本课知识点。视频生产只读取被批准的一套方案。",
  },
  {
    key: "ppt_outline",
    title: "PPT 大纲",
    group: "PPT",
    rendererKey: "ppt-outline",
    capability: "text_generation",
    dependsOn: ["lesson_plan"],
    skippable: true,
    description: "把已批准教案转化为分章节的 PPT 大纲，确定页面结构与页数。",
  },
  {
    key: "ppt_pages",
    title: "页面脚本",
    group: "PPT",
    rendererKey: "ppt-pages",
    capability: "text_generation",
    dependsOn: ["ppt_outline"],
    skippable: true,
    description: "为每一页生成标题、正文块与讲稿备注；支持整页重生成或单页修订。",
  },
  {
    key: "ppt_assets",
    title: "页面配图",
    group: "PPT",
    rendererKey: "ppt-assets",
    capability: "image_generation",
    dependsOn: ["ppt_pages"],
    skippable: true,
    description: "为需要图示的页面生成教学插图；封面为设计封面，正文页保持纯白底。",
  },
  {
    key: "ppt_preview",
    title: "整册预览",
    group: "PPT",
    rendererKey: "ppt-preview",
    capability: null,
    dependsOn: ["ppt_assets"],
    skippable: true,
    description: "按最终版式预览整份 PPT，确认关键样张后进入导出。",
  },
  {
    key: "ppt_export",
    title: "PPTX 导出",
    group: "PPT",
    rendererKey: "ppt-export",
    capability: "pptx_render",
    dependsOn: ["ppt_preview"],
    skippable: true,
    description: "后台组装 PPTX 并进行质量检查，生成可下载的正式文件。",
  },
  {
    key: "video_master_script",
    title: "母版剧本",
    group: "视频",
    rendererKey: "video-master-script",
    capability: "text_generation",
    dependsOn: ["lesson_plan", "intro_design"],
    skippable: true,
    description: "读取被批准的导入方案与教案，完成课程适配后的完整视频剧本（分场景与旁白）。",
  },
  {
    key: "video_visual_direction",
    title: "视觉方向",
    group: "视频",
    rendererKey: "video-visual-direction",
    capability: "text_generation",
    dependsOn: ["video_master_script"],
    skippable: true,
    description: "确定整片的美术风格、色板、角色与场景设定，作为后续所有画面的统一依据。",
  },
  {
    key: "video_master_image",
    title: "视觉母图",
    group: "视频",
    rendererKey: "video-master-image",
    capability: "image_generation",
    dependsOn: ["video_visual_direction"],
    skippable: true,
    description: "生成统一画风的视觉母图候选并选定一张，后续图片资产以母图为风格基准。",
  },
  {
    key: "video_rough_storyboard",
    title: "粗分镜",
    group: "视频",
    rendererKey: "video-rough-storyboard",
    capability: "text_generation",
    dependsOn: ["video_master_image"],
    skippable: true,
    description: "把剧本拆成带镜头号的粗分镜（画面内容、机位、时长、旁白），生成 shot_id 列表。",
  },
  {
    key: "video_image_assets",
    title: "图片资产",
    group: "视频",
    rendererKey: "video-image-assets",
    capability: "image_generation",
    dependsOn: ["video_rough_storyboard"],
    skippable: true,
    description:
      "依据粗分镜和视觉母图批量生成镜头首帧图片资产；此步骤必须在细分镜之前完成，支持单张重试与部分成功。",
  },
  {
    key: "video_fine_storyboard",
    title: "细分镜",
    group: "视频",
    rendererKey: "video-fine-storyboard",
    capability: "text_generation",
    dependsOn: ["video_image_assets"],
    skippable: true,
    description: "在图片资产基础上细化每个镜头：绑定首帧、运动方式、台词与字幕文本。",
  },
  {
    key: "video_shot_prompts",
    title: "镜头提示词",
    group: "视频",
    rendererKey: "video-shot-prompts",
    capability: "text_generation",
    dependsOn: ["video_fine_storyboard"],
    skippable: true,
    description: "为每个镜头生成视频模型提示词（含首帧引用与负向提示），可逐镜头查看与编辑。",
  },
  {
    key: "video_clips",
    title: "视频片段",
    group: "视频",
    rendererKey: "video-clips",
    capability: "video_generation",
    dependsOn: ["video_shot_prompts"],
    skippable: true,
    description:
      "按镜头提示词逐镜头生成视频片段（clip），支持单镜头重试与部分成功；每个镜头只保留一个被批准的片段。",
  },
  {
    key: "video_audio_subtitle",
    title: "声音与字幕",
    group: "视频",
    rendererKey: "video-audio-subtitle",
    capability: "tts",
    dependsOn: ["video_clips"],
    skippable: true,
    description: "生成旁白配音与字幕轨，并与片段时间轴对齐。",
  },
  {
    key: "video_final_cut",
    title: "剪辑成片",
    group: "视频",
    rendererKey: "video-final-cut",
    capability: "video_compose",
    dependsOn: ["video_audio_subtitle"],
    skippable: true,
    description: "把被批准的片段、配音与字幕合成最终成片，输出可预览与下载的视频文件。",
  },
  {
    key: "delivery",
    title: "交付清单",
    group: "交付",
    rendererKey: "delivery",
    capability: null,
    dependsOn: ["lesson_plan"],
    skippable: false,
    description: "汇总本课的教案、PPT 与视频产物，检查交付阻断项并打包正式交付物。",
  },
];

export const nodeByKey: ReadonlyMap<string, WorkflowNodeDef> = new Map(
  LESSON_NODES.map((node) => [node.key, node]),
);

export function getNodeDef(nodeKey: string): WorkflowNodeDef | undefined {
  return nodeByKey.get(nodeKey);
}

/** 下游节点键（直接依赖该节点的）。 */
export function directDownstreamKeys(nodeKey: string): string[] {
  return LESSON_NODES.filter((n) => n.dependsOn.includes(nodeKey)).map((n) => n.key);
}
