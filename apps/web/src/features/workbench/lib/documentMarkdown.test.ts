import { describe, expect, it } from "vitest";
import { lessonPlanData } from "@/features/content-definition/fixtures";
import {
  parseLessonPlan,
  parseMasterScript,
  serializeLessonPlan,
  serializeMasterScript,
  type ScriptScene,
} from "@/features/workbench/lib/documentMarkdown";

const scenes: ScriptScene[] = [
  {
    action: "果汁依次落桌。",
    dialogue: "哪一瓶更多？",
    duration: "0:00—0:18",
    narration: "三个小组带来果汁。",
    sound: "轻快木琴。",
    title: "标签上的谜题",
  },
];

describe("工作台连续稿件格式", () => {
  it("教案可在结构化数据与连续正文之间往返", () => {
    const markdown = serializeLessonPlan(
      lessonPlanData,
      "百分数的意义",
      "六年级数学 · 第 1 课时",
    ).replace("理解百分数表示一个数是另一个数的百分之几", "理解百分数表达整体与部分的关系");
    const parsed = parseLessonPlan(markdown, lessonPlanData);

    expect(markdown).toContain("# 百分数的意义");
    expect(markdown).toContain("## 教学过程");
    expect(parsed.teaching_content).toContain("整体与部分的关系");
    expect(parsed.objectives).toEqual(lessonPlanData.objectives);
  });

  it("母版剧本保留故事场次与声音意图", () => {
    const markdown = serializeMasterScript(
      "果汁标签侦探",
      "让学生发现公平比较的问题。",
      scenes,
      "三张标签并排出现，等待学生判断。",
    );
    const parsed = parseMasterScript(markdown, {
      scenes,
      summary: "让学生发现公平比较的问题。",
      title: "果汁标签侦探",
    });

    expect(markdown).toContain("## 场次 1｜标签上的谜题（0:00—0:18）");
    expect(markdown).toContain("三张标签并排出现，等待学生判断。");
    expect(markdown).not.toContain("视频导入母版剧本");
    expect(parsed.scenes).toHaveLength(1);
    expect(parsed.scenes[0]).toMatchObject({
      action: "果汁依次落桌。",
      duration: "0:00—0:18",
      sound: "轻快木琴。",
      title: "标签上的谜题",
    });
  });
});
