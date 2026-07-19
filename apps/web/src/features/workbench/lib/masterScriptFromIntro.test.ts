import { describe, expect, it } from "vitest";
import { introOptions } from "@/features/intro-options/data";
import {
  createMasterScriptFromIntro,
  masterScriptNeedsRefresh,
} from "@/features/workbench/lib/masterScriptFromIntro";

describe("createMasterScriptFromIntro", () => {
  it("把正式采用方案转换为完整的三场故事", () => {
    const option = introOptions[1];
    if (!option) throw new Error("缺少测试方案");

    const script = createMasterScriptFromIntro(option);

    expect(script.title).toBe(option.title);
    expect(script.summary).toContain(option.firstQuestion);
    expect(script.scenes).toHaveLength(3);
    expect(script.scenes[2]?.action).toBe(option.handoff);
  });

  it("识别正式导入版本与已保存剧本来源不一致", () => {
    const adopted = { key: "INTRO-SCI-01", revision: 2 };

    expect(
      masterScriptNeedsRefresh({ sourceIntroKey: adopted.key, sourceIntroRevision: 1 }, adopted),
    ).toBe(true);
    expect(masterScriptNeedsRefresh({}, adopted)).toBe(false);
  });
});
