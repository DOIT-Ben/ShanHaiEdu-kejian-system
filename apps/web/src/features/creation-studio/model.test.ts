import { describe, expect, it } from "vitest";
import { buildCreationResultId, clampCreationCandidate } from "@/features/creation-studio/model";

describe("buildCreationResultId", () => {
  it("把创作轮次纳入结果身份，避免新一轮覆盖旧作品", () => {
    expect(buildCreationResultId("image", 1, 0)).not.toBe(buildCreationResultId("image", 2, 0));
    expect(buildCreationResultId("image", 2, 0)).toBe("creation-image-generation-2-candidate-1");
  });

  it("生成数量减少时把当前作品收敛到仍存在的候选", () => {
    expect(clampCreationCandidate(3, "2")).toBe(1);
    expect(clampCreationCandidate(-1, "4")).toBe(0);
  });
});
