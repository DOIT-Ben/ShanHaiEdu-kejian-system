import type { WorkflowStatus } from "@/entities/workflow/model";

export type VideoStoryBeat = {
  assets: string;
  event: string;
  time: string;
  title: string;
};

export type VideoShot = {
  beat: string;
  duration: number;
  id: string;
  movement: string;
  status: WorkflowStatus;
};

export type VideoAsset = {
  id: string;
  status: "needs_generation" | "ready";
  title: string;
  type: string;
};

export type VideoStyle = {
  id: string;
  image: string;
  name: string;
};

export const demoVideoTitle = "果汁标签侦探";

export const demoStoryBeats: VideoStoryBeat[] = [
  {
    time: "0—8 秒",
    title: "三瓶果汁进入画面",
    event: "同样大小的三瓶果汁依次落在桌面，建立比较对象。",
    assets: "桌面场景、三瓶果汁",
  },
  {
    time: "8—18 秒",
    title: "发现不同标签",
    event: "镜头依次靠近三张不完整标签，人物观察数字差异。",
    assets: "果汁标签、人物手部",
  },
  {
    time: "18—30 秒",
    title: "数字带来误导",
    event: "人物先按数字大小排序，又发现每瓶总容量不同。",
    assets: "数字卡、容量标记",
  },
  {
    time: "30—43 秒",
    title: "补齐比较信息",
    event: "完整标签并排出现，部分与整体信息同时可见。",
    assets: "三张完整标签",
  },
  {
    time: "43—55 秒",
    title: "停在课堂首问",
    event: "人物停下选择，镜头定格，留下公平比较的问题。",
    assets: "定格画面、课堂首问",
  },
];

export const demoVideoShots: VideoShot[] = [
  {
    id: "镜头 1",
    duration: 10,
    beat: "三瓶果汁依次落在桌面，建立比较对象",
    movement: "固定中景，轻微向前推进",
    status: "approved",
  },
  {
    id: "镜头 2",
    duration: 10,
    beat: "镜头依次靠近三张标签，人物发现数字不同",
    movement: "从左向右平移",
    status: "review_required",
  },
  {
    id: "镜头 3",
    duration: 15,
    beat: "人物按数字排序后发现总容量也不同",
    movement: "俯拍转为人物近景",
    status: "partially_completed",
  },
  {
    id: "镜头 4",
    duration: 10,
    beat: "完整标签并排，部分与整体信息同时可见",
    movement: "稳定俯拍",
    status: "ready",
  },
  {
    id: "镜头 5",
    duration: 10,
    beat: "人物停下选择，画面定格在课堂首问",
    movement: "缓慢拉远后停住",
    status: "not_ready",
  },
];

export const demoVideoStyles: VideoStyle[] = [
  {
    id: "paper",
    name: "纸艺微缩课堂",
    image: "/assets/creation/video-label-detective.svg",
  },
  {
    id: "clay",
    name: "柔和黏土定格",
    image: "/assets/creation/video-classroom-question.svg",
  },
  {
    id: "clean",
    name: "清透实物插画",
    image: "/assets/creation/juice-observation.svg",
  },
];

export const demoVideoAssets: VideoAsset[] = [
  { id: "character", type: "人物", title: "观察标签的六年级学生", status: "ready" },
  { id: "scene", type: "场景", title: "自然光下的木质桌面", status: "ready" },
  { id: "props", type: "道具", title: "三瓶不同标签的果汁", status: "needs_generation" },
  { id: "keyframe", type: "镜头关键帧", title: "三张完整标签并排", status: "needs_generation" },
];

function topicName(knowledgePoint: string) {
  return knowledgePoint.trim() || "本课知识点";
}

export function createTopicStoryBeats(knowledgePoint: string): VideoStoryBeat[] {
  const topic = topicName(knowledgePoint);
  return [
    {
      time: "0—10 秒",
      title: "进入教材情境",
      event: `从学生熟悉的生活画面切入${topic}，先呈现完整情境。`,
      assets: "教材情境、观察对象",
    },
    {
      time: "10—22 秒",
      title: "发现关键线索",
      event: `镜头靠近与${topic}有关的关键信息，让学生先观察差异。`,
      assets: "关键信息、人物视线",
    },
    {
      time: "22—34 秒",
      title: "出现不同想法",
      event: "两种直观判断依次出现，保留冲突，不直接给出结论。",
      assets: "两种想法、比较画面",
    },
    {
      time: "34—46 秒",
      title: "补齐判断依据",
      event: `画面补充探究${topic}所需的条件，引导学生重新检查。`,
      assets: "补充线索、关系图示",
    },
    {
      time: "46—55 秒",
      title: "把问题带回课堂",
      event: `画面停在与${topic}有关的关键问题上，等待学生表达理由。`,
      assets: "定格画面、课堂首问",
    },
  ];
}

export function createTopicVideoShots(knowledgePoint: string): VideoShot[] {
  const topic = topicName(knowledgePoint);
  return [
    {
      id: "镜头 1",
      duration: 10,
      beat: `呈现与${topic}有关的完整课堂情境`,
      movement: "固定中景，轻微向前推进",
      status: "approved",
    },
    {
      id: "镜头 2",
      duration: 12,
      beat: "镜头靠近关键信息，人物开始观察差异",
      movement: "从整体平移到局部",
      status: "review_required",
    },
    {
      id: "镜头 3",
      duration: 12,
      beat: "两种不同判断依次出现，留下思考冲突",
      movement: "俯拍转为人物近景",
      status: "partially_completed",
    },
    {
      id: "镜头 4",
      duration: 12,
      beat: `补齐探究${topic}所需的条件与图示`,
      movement: "稳定俯拍",
      status: "ready",
    },
    {
      id: "镜头 5",
      duration: 9,
      beat: "人物停下判断，画面定格在课堂首问",
      movement: "缓慢拉远后停住",
      status: "not_ready",
    },
  ];
}

export function createTopicVideoStyles(knowledgePoint: string): VideoStyle[] {
  const topic = topicName(knowledgePoint);
  return [
    {
      id: "paper",
      name: `${topic} · 纸艺课堂`,
      image: "/assets/creation/video-label-detective.svg",
    },
    {
      id: "clay",
      name: `${topic} · 温和定格`,
      image: "/assets/creation/video-classroom-question.svg",
    },
    {
      id: "clean",
      name: `${topic} · 清透插画`,
      image: "/assets/creation/juice-observation.svg",
    },
  ];
}

export function createTopicVideoAssets(knowledgePoint: string): VideoAsset[] {
  const topic = topicName(knowledgePoint);
  return [
    { id: "character", type: "人物", title: "参与观察与表达的小学生", status: "ready" },
    { id: "scene", type: "场景", title: `${topic}的教材情境`, status: "ready" },
    {
      id: "props",
      type: "教具",
      title: `解释${topic}所需的图示或实物`,
      status: "needs_generation",
    },
    { id: "keyframe", type: "镜头关键帧", title: "课堂首问定格画面", status: "needs_generation" },
  ];
}
