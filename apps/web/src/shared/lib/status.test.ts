import { describe, expect, it } from "vitest";
import { getNodeStatusMeta, getBranchStateMeta, isTaskActive } from "@/shared/lib/status";
import { STEPS, getStep, stepKeyForNode } from "@/entities/workflow";
import { shotDisplayName, pageDisplayName } from "@/shared/lib/teacherLanguage";

describe("15 态节点状态映射（workflow-node-status）", () => {
  const ALL = [
    "disabled",
    "not_ready",
    "ready",
    "draft",
    "queued",
    "running",
    "review_required",
    "approved",
    "partially_completed",
    "failed",
    "paused",
    "cancel_requested",
    "cancelled",
    "stale",
    "skipped",
  ];

  it("每个状态都有教师语言标签（无英文残留）", () => {
    for (const status of ALL) {
      const meta = getNodeStatusMeta(status);
      expect(meta.label, status).toBeTruthy();
      expect(meta.label, status).not.toMatch(/[A-Za-z_]/);
    }
  });

  it("review_required 使用「等待你确认」；stale 使用「内容已变化」措辞", () => {
    expect(getNodeStatusMeta("review_required").label).toContain("等待你确认");
    expect(getNodeStatusMeta("stale").label).toContain("内容已变化");
  });

  it("disabled 与 skipped 语义不同", () => {
    expect(getNodeStatusMeta("disabled").label).not.toBe(getNodeStatusMeta("skipped").label);
    expect(getBranchStateMeta("disabled").label).not.toBe(getBranchStateMeta("skipped").label);
  });
});

describe("流程栏步骤定义", () => {
  it("视频六步严格按依赖顺序排列", () => {
    const videoSteps = STEPS.filter((s) => s.group === "video").map((s) => s.nodeKey);
    expect(videoSteps).toEqual([
      "video_script",
      "video_storyboard",
      "video_style",
      "video_assets",
      "video_clips",
      "video_compose",
    ]);
  });

  it("教案节点区分生成/确认两个入口", () => {
    expect(stepKeyForNode("lesson_plan", "running")).toBe("lesson-plan");
    expect(stepKeyForNode("lesson_plan", "review_required")).toBe("lesson-plan-confirm");
    expect(stepKeyForNode("lesson_plan", "approved")).toBe("lesson-plan-confirm");
  });

  it("link 类步骤没有 nodeKey（教材/课时/下载）", () => {
    for (const key of ["textbook", "lesson-division", "download"]) {
      const step = getStep(key)!;
      expect(step.kind).toBe("link");
      expect(step.nodeKey).toBeNull();
    }
  });
});

describe("教师语言（禁止 shot_id/page_key 直出）", () => {
  it("镜头与页面使用中文序号", () => {
    expect(shotDisplayName(2)).toBe("镜头2");
    expect(pageDisplayName(3)).toBe("第3页");
  });
});

describe("任务活跃态判断", () => {
  it("排队/运行/等待模型/下载中/请求停止 均为活跃", () => {
    for (const s of ["queued", "running", "waiting_provider", "downloading", "cancel_requested"]) {
      expect(isTaskActive(s), s).toBe(true);
    }
    for (const s of ["completed", "failed", "cancelled", "partially_completed"]) {
      expect(isTaskActive(s), s).toBe(false);
    }
  });
});
