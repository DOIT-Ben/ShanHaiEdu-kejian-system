import { describe, expect, it } from "vitest";
import { markIntroDependentsStale } from "@/features/intro-options/invalidateDependents";
import { createMockRuntimeStore } from "@/shared/api/mocks/runtime";

describe("markIntroDependentsStale", () => {
  it("只让已有下游内容过期，并保留已有节点标题", () => {
    localStorage.clear();
    const store = createMockRuntimeStore({
      storage: localStorage,
      storageKey: "intro-dependents-test",
    });
    const projectId = "project-a";
    const lessonId = "lesson-a";
    store.updateNodeState(projectId, lessonId, "master-script", {
      status: "approved",
      title: "自定义母版剧本",
    });
    store.saveDraft(
      `project:${projectId}:lesson:${lessonId}:rough-storyboard`,
      { items: [] },
      { lessonId, nodeKey: "rough-storyboard", projectId },
    );

    markIntroDependentsStale(store.getState(), projectId, lessonId, store);

    expect(store.getNodeState(projectId, lessonId, "master-script")).toMatchObject({
      stale_reason: { summary: "课堂导入已改用新方案" },
      status: "stale",
      title: "自定义母版剧本",
    });
    expect(store.getNodeState(projectId, lessonId, "rough-storyboard")).toMatchObject({
      status: "stale",
      title: "安排故事镜头",
    });
    expect(store.getNodeState(projectId, lessonId, "video-style")).toBeUndefined();
  });
});
