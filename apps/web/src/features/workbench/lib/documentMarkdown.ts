import type { ContentData } from "@/features/content-definition/model";

export type ScriptScene = {
  action: string;
  dialogue: string;
  duration: string;
  narration: string;
  sound: string;
  title: string;
};

function asString(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function asList(value: unknown, fallback: string[] = []) {
  return Array.isArray(value) ? value.map(String) : fallback;
}

function sectionMap(markdown: string) {
  const result: Record<string, string[]> = {};
  let current = "";
  for (const line of markdown.replace(/\r/g, "").split("\n")) {
    const heading = /^##\s+(.+)$/.exec(line.trim());
    if (heading) {
      current = heading[1]?.trim() ?? "";
      result[current] = [];
    } else if (current) {
      result[current]?.push(line);
    }
  }
  return result;
}

function sectionText(sections: Record<string, string[]>, label: string, fallback: string) {
  const value = sections[label]?.join("\n").trim();
  return value || fallback;
}

function sectionList(sections: Record<string, string[]>, label: string, fallback: string[]) {
  const values = (sections[label] ?? [])
    .map((line) => line.replace(/^[-*]\s+/, "").trim())
    .filter(Boolean);
  return values.length > 0 ? values : fallback;
}

function quoteLines(value: string) {
  return value
    .split("\n")
    .map((line) => `> ${line}`)
    .join("\n");
}

function listLines(value: unknown) {
  return asList(value)
    .map((item) => `- ${item}`)
    .join("\n");
}

export function serializeLessonPlan(data: ContentData, title: string, subtitle: string) {
  return [
    `# ${title}`,
    `> ${subtitle}`,
    "",
    "## 教学内容",
    asString(data.teaching_content),
    "",
    "## 教材分析",
    asString(data.textbook_analysis),
    "",
    "## 学情分析",
    asString(data.student_analysis),
    "",
    "## 设计意图",
    asString(data.design_intent),
    "",
    "## 教学目标",
    listLines(data.objectives),
    "",
    "## 教学重难点及突破策略",
    asString(data.key_points),
    "",
    "## 教学准备",
    listLines(data.preparation),
    "",
    "## 教学过程",
    listLines(data.process),
    "",
    "## 板书设计",
    quoteLines(asString(data.board_design)),
    "",
    "## 课堂总结",
    asString(data.summary),
    "",
    "## 分层作业",
    listLines(data.homework),
    "",
    "## 教学反思",
    asString(data.reflection),
  ].join("\n");
}

export function parseLessonPlan(markdown: string, fallback: ContentData): ContentData {
  const sections = sectionMap(markdown);
  return {
    ...fallback,
    teaching_content: sectionText(sections, "教学内容", asString(fallback.teaching_content)),
    textbook_analysis: sectionText(sections, "教材分析", asString(fallback.textbook_analysis)),
    student_analysis: sectionText(sections, "学情分析", asString(fallback.student_analysis)),
    design_intent: sectionText(sections, "设计意图", asString(fallback.design_intent)),
    objectives: sectionList(sections, "教学目标", asList(fallback.objectives)),
    key_points: sectionText(sections, "教学重难点及突破策略", asString(fallback.key_points)),
    preparation: sectionList(sections, "教学准备", asList(fallback.preparation)),
    process: sectionList(sections, "教学过程", asList(fallback.process)),
    board_design: sectionText(sections, "板书设计", asString(fallback.board_design)).replace(
      /^>\s?/gm,
      "",
    ),
    summary: sectionText(sections, "课堂总结", asString(fallback.summary)),
    homework: sectionList(sections, "分层作业", asList(fallback.homework)),
    reflection: sectionText(sections, "教学反思", asString(fallback.reflection)),
  };
}

function labeledLines(scene: ScriptScene) {
  return [
    `**画面动作**：${scene.action}`,
    `**旁白**：${scene.narration}`,
    scene.dialogue ? `**对白**：${scene.dialogue}` : "**对白**：无",
    `**声音意图**：${scene.sound}`,
  ];
}

export function serializeMasterScript(
  title: string,
  summary: string,
  scenes: ScriptScene[],
  handoff: string,
) {
  return [
    `# ${title}`,
    "## 故事梗概",
    summary,
    "",
    ...scenes.flatMap((scene, index) => {
      const sceneTitle = scene.title.replace(/^场次\s*\d+\s*·\s*/, "");
      return [
        `## 场次 ${String(index + 1)}｜${sceneTitle}（${scene.duration}）`,
        ...labeledLines(scene),
        "",
      ];
    }),
    "## 课堂交接",
    handoff,
  ].join("\n");
}

function labeledSection(lines: string[]) {
  const result: Record<string, string> = {};
  let current = "";
  for (const line of lines) {
    const match = /^\*\*(.+?)\*\*：\s*(.*)$/.exec(line.trim());
    if (match) {
      current = match[1] ?? "";
      result[current] = match[2] ?? "";
    } else if (current && line.trim()) {
      result[current] = `${result[current] ?? ""}\n${line.trim()}`.trim();
    }
  }
  return result;
}

export function parseMasterScript(
  markdown: string,
  fallback: { scenes: ScriptScene[]; summary: string; title: string },
) {
  const lines = markdown.replace(/\r/g, "").split("\n");
  const title =
    lines
      .find((line) => /^#\s+/.test(line))
      ?.replace(/^#\s+/, "")
      .trim() || fallback.title;
  const sections: Array<{ heading: string; lines: string[] }> = [];
  let current: { heading: string; lines: string[] } | undefined;
  for (const line of lines) {
    const heading = /^##\s+(.+)$/.exec(line.trim());
    if (heading) {
      current = { heading: heading[1]?.trim() ?? "", lines: [] };
      sections.push(current);
    } else if (current) {
      current.lines.push(line);
    }
  }
  const summarySection = sections.find((section) => section.heading === "故事梗概");
  const summary = summarySection?.lines.join("\n").trim() || fallback.summary;
  const sceneSections = sections.filter((section) => /^场次\s+\d+/.test(section.heading));
  const scenes = sceneSections.length
    ? sceneSections.map((section, index) => {
        const headingBody = section.heading.replace(/^场次\s+\d+\s*[｜|]\s*/, "");
        const durationMatch = /（([^）]+)）$/.exec(headingBody);
        const sceneTitle = headingBody.replace(/（[^）]+）$/, "").trim();
        const labels = labeledSection(section.lines);
        const previous = fallback.scenes[index] ?? fallback.scenes[0];
        return {
          action: labels["画面动作"] ?? previous?.action ?? "",
          dialogue: labels["对白"] === "无" ? "" : (labels["对白"] ?? previous?.dialogue ?? ""),
          duration: durationMatch?.[1] ?? previous?.duration ?? "待安排",
          narration: labels["旁白"] ?? previous?.narration ?? "",
          sound: labels["声音意图"] ?? previous?.sound ?? "",
          title: sceneTitle || previous?.title || `场次 ${String(index + 1)}`,
        };
      })
    : fallback.scenes;
  return { scenes, summary, title };
}
