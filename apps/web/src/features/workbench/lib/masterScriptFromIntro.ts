import type { IntroOption } from "@/features/intro-options/model";
import type { ScriptScene } from "@/features/workbench/lib/documentMarkdown";

export function masterScriptNeedsRefresh(
  saved: { sourceIntroKey?: string; sourceIntroRevision?: number } | undefined,
  adopted: { key: string; revision: number },
) {
  if (!saved) return false;
  if (saved.sourceIntroKey !== undefined || saved.sourceIntroRevision !== undefined) {
    return saved.sourceIntroKey !== adopted.key || saved.sourceIntroRevision !== adopted.revision;
  }
  return false;
}

function timestamp(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function createMasterScriptFromIntro(option: IntroOption): {
  scenes: ScriptScene[];
  summary: string;
  title: string;
} {
  const firstEnd = Math.max(10, Math.round(option.duration * 0.34));
  const secondEnd = Math.max(firstEnd + 10, Math.round(option.duration * 0.7));
  const end = Math.max(secondEnd + 5, option.duration);
  return {
    title: option.title,
    summary: `${option.concept} 故事围绕“${option.firstQuestion}”逐步展开，在出现关键线索后停住，把判断留给学生。`,
    scenes: [
      {
        title: "问题出现",
        duration: `0:00—${timestamp(firstEnd)}`,
        action: option.concept,
        narration: option.hook,
        dialogue: "",
        sound: "轻快、清楚的开场音乐，关键画面出现时自然收低。",
      },
      {
        title: "寻找比较线索",
        duration: `${timestamp(firstEnd)}—${timestamp(secondEnd)}`,
        action: option.courseAnchor,
        narration: "画面补充比较所需的信息，但不直接给出结论。",
        dialogue: option.firstQuestion,
        sound: "保留观察和思考的停顿，让问题被听清。",
      },
      {
        title: "把问题带回课堂",
        duration: `${timestamp(secondEnd)}—${timestamp(end)}`,
        action: option.handoff,
        narration: "线索已经出现，人物停下判断，把最后一步留给课堂讨论。",
        dialogue: option.firstQuestion,
        sound: "音乐收束，结尾保留两秒安静思考。",
      },
    ],
  };
}
