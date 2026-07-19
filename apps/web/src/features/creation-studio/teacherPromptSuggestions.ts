import type { StudioType } from "@/features/creation-studio/model";

export type TeacherPromptSuggestion = {
  label: string;
  text: string;
};

export const teacherPromptSuggestions: Record<StudioType, TeacherPromptSuggestion[]> = {
  image: [
    { label: "留出板书区", text: "画面右侧留出干净的提问或板书空间。" },
    { label: "突出数学关系", text: "让数量以及部分与整体的关系一眼可见。" },
    { label: "更适合低年级", text: "造型亲切、色彩柔和，适合小学低年级学生观看。" },
    { label: "像真实课堂", text: "使用自然光和真实教具质感，不要像商业海报。" },
  ],
  video: [
    { label: "动作慢一点", text: "动作节奏放慢，让小学生能看清每一步变化。" },
    { label: "先观察再揭晓", text: "先留出观察时间，再展示关键变化。" },
    { label: "结尾留个问题", text: "结尾停留在可供老师提问的画面。" },
    { label: "适合无声播放", text: "只看画面也能理解主要变化。" },
  ],
  presentation: [
    { label: "一页一个重点", text: "每一页只讲清一个知识点，不堆叠信息。" },
    { label: "增加课堂提问", text: "在关键页面加入能让学生先观察再回答的问题。" },
    { label: "适合教室投影", text: "文字和图形要大而清楚，后排学生也能看见。" },
    { label: "多用直观图示", text: "优先用小学阶段熟悉的实物和关系图解释概念。" },
  ],
};

export function appendTeacherSuggestion(description: string, suggestion: TeacherPromptSuggestion) {
  const trimmed = description.trim();
  if (trimmed.includes(suggestion.text)) return trimmed;
  return `${trimmed}${trimmed ? "\n" : ""}${suggestion.text}`;
}
