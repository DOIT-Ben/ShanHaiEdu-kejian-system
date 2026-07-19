import { describe, expect, it } from "vitest";
import { parseWorkflowStatus } from "@/entities/workflow/model";

describe("parseWorkflowStatus", () => {
  it("保留合同中已知状态", () => {
    expect(parseWorkflowStatus("review_required")).toBe("review_required");
  });

  it("将未知状态映射为可恢复提示状态", () => {
    expect(parseWorkflowStatus("future_status")).toBe("unknown");
  });
});
