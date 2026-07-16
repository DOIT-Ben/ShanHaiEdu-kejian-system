import type { PromptVersion } from "@/shared/api/types";
import { getDb, nextId, minutesAgo } from "../db";
import { getNodeDef } from "@/entities/workflow/nodes";

const RUNTIME_CONTRACT = `【平台运行契约（只读）】
1. 内容安全：产出面向小学三年级学生，禁止暴力、恐怖、歧视与广告内容；术语遵循人教版教材表述。
2. 输出结构：必须严格按照本节点的输出 Schema 返回结构化 JSON，字段不可缺失或改名。
3. 资产白名单：仅可引用本课已批准的上游产物与资产库中状态为「已批准」的资产。
4. 版权限制：不得要求模型模仿具体在世画家或使用受版权保护的角色形象。`;

const NODE_PROMPTS: Record<string, string> = {
  lesson_plan: `你是一名资深小学数学教研员。请基于教材证据与课时边界，为本课时生成十二部分结构化教案。

要求：
- 教学目标从「知识技能、过程方法、情感态度」三个维度撰写，并与课程标准中的核心素养对应；
- 教学过程划分为 4-6 个环节，每个环节包含教师活动、学生活动与设计意图，并标注时长；
- 重难点表述具体、可观察，避免空泛；
- 板书设计用文字描绘出版式结构；
- 练习与作业分层（基础 / 变式 / 拓展）。

课时信息与教材证据由系统自动注入上下文。`,
  intro_design: `你是一名儿童教育内容创意师。请独立创作本课的导入创意方案，分「科普向、应用向、故事向」三类，每类三套，共九套。

要求：
- 创意必须独立成立、有趣且适合三年级学生，不从教案内容直接推导；
- 每套方案给出：标题、创意概要、90 秒左右的叙事脚本、画面风格提示；
- 每套方案附「课程锚点」：说明该创意如何自然连接到本课知识点（锚点连接课程，创意保持独立）；
- 三类九套之间题材不得重复。`,
  ppt_outline: `你是一名课件设计师。请把已批准的教案转化为教学 PPT 大纲。

要求：
- 按「课题导入 → 探究新知 → 深化理解 → 巩固练习 → 课堂小结」组织章节；
- 每章节列出页面标题清单，总页数控制在 12-16 页；
- 页面标题使用面向课堂展示的语言。`,
  ppt_pages: `你是一名课件设计师。请为 PPT 大纲中的每一页撰写页面脚本。

要求：
- 每页给出标题、内容块（正文 / 要点列表 / 例题 / 互动提问 / 配图占位 / 公式）与讲稿备注；
- 正文页保持信息克制，每页不超过 5 个要点；
- 例题页保留完整题目文本；封面页只含课题与出处信息。`,
  ppt_assets: `你是一名教学插画生成助手。请为标记了配图占位的页面生成教学插图提示词并产出插图。

要求：
- 插图风格统一：明快扁平教学插画，主色调与品牌蓝 #2854E8 协调；
- 数学图示（等分图、分数涂色图）必须准确无误；
- 不得包含文字错误；画面简洁不喧宾夺主。`,
  ppt_export: `系统节点：按最终确认的页面脚本与配图组装 PPTX 文件，执行版式与质量检查（封面为设计封面，正文页纯白底）。`,
  video_master_script: `你是一名少儿科普视频编剧。请基于被批准的导入创意方案与本课教案，完成课程适配后的完整母版剧本。

要求：
- 保留创意方案的核心叙事，不得偏离已锁定的创意设定；
- 在锚点位置自然引入本课知识点；
- 输出分场景结构：场景标题、旁白（口语化、面向 8-9 岁儿童）、画面构想、时长；
- 总时长 90 秒左右。`,
  video_visual_direction: `你是一名动画美术指导。请为本片确定统一的视觉方向。

要求：
- 给出风格名称、风格关键词、色板（5 个以内主色）、角色设定与场景设定说明；
- 风格适合小学生观看，画面温暖明亮；
- 设定需可被后续所有图片与视频生成继承。`,
  video_master_image: `你是一名概念画师。请依据视觉方向生成视觉母图候选。

要求：
- 母图需完整呈现主角色、主场景与整体色调，作为全片风格基准；
- 生成 3 张候选供挑选；
- 构图留有安全边距，适配 16:9。`,
  video_rough_storyboard: `你是一名分镜师。请把母版剧本拆解为粗分镜。

要求：
- 每个镜头包含：镜头号、所属场景、画面描述、机位/运镜、时长、对应旁白；
- 单镜头时长 5-20 秒，总时长与剧本一致；
- 输出 shot_id 顺序列表。`,
  video_image_assets: `你是一名教学动画画师。请依据粗分镜与视觉母图，为每个镜头生成首帧图片资产。

要求：
- 严格继承母图的角色造型、色板与质感（此步骤在粗分镜之后、细分镜之前执行）;
- 每张图对应镜头描述的关键画面；
- 支持逐张重试，失败镜头单独标记。`,
  video_fine_storyboard: `你是一名分镜师。请在图片资产基础上细化每个镜头。

要求：
- 为每个镜头绑定首帧图片资产；
- 补充运动方式（推拉摇移/元素动效）、台词与字幕文本；
- 字幕逐句对应旁白，单行不超过 18 字。`,
  video_shot_prompts: `你是一名视频生成提示词工程师。请为每个镜头生成视频模型提示词。

要求：
- 提示词包含：画面内容、风格约束（引用视觉母图）、运镜、时长；
- 附负向提示词（畸形、文字错误、恐怖元素等）；
- 引用该镜头的首帧图片资产作为 first_frame。`,
  video_clips: `系统节点：按镜头提示词逐镜头调用视频生成，产出各镜头片段（clip），支持单镜头重试与部分成功。`,
  video_audio_subtitle: `你是一名配音与字幕合成助手。请为成片生成旁白配音与字幕轨。

要求：
- 声线：亲切童声（女），语速适中；
- 字幕与旁白逐句对齐，输出 SRT；
- 术语读音准确（如「二分之一」）。`,
  video_final_cut: `系统节点：把每个镜头被批准的片段按顺序拼接，混入配音与字幕，输出最终成片（1080P MP4）。`,
  delivery: `系统节点：汇总本课已批准产物，检查交付阻断项，打包交付物并生成质量报告。`,
};

export function promptTextForNode(nodeKey: string): string {
  return NODE_PROMPTS[nodeKey] ?? `${getNodeDef(nodeKey)?.title ?? nodeKey} 生成提示词。`;
}

export function makePromptVersion(input: {
  nodeKey: string;
  versionNumber: number;
  source?: "system" | "edited" | "revision";
  editablePrompt?: string;
  basePromptVersionId?: string | null;
  createdMinutesAgo?: number;
}): PromptVersion {
  const db = getDb();
  return {
    prompt_version_id: nextId(db, "pv"),
    version_number: input.versionNumber,
    editable_prompt: input.editablePrompt ?? promptTextForNode(input.nodeKey),
    runtime_contract: RUNTIME_CONTRACT,
    source: input.source ?? "system",
    base_prompt_version_id: input.basePromptVersionId ?? null,
    created_at: minutesAgo(input.createdMinutesAgo ?? 60),
  };
}

export { RUNTIME_CONTRACT };
