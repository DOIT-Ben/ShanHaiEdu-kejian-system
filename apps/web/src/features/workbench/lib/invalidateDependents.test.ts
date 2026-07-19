import { beforeEach, describe, expect, it } from "vitest";
import {
  markLessonDivisionDependentsStale,
  markLessonDivisionDependentsStaleForLessons,
  markLessonPlanDependentsStale,
} from "@/features/workbench/lib/invalidateDependents";
import { createMockRuntimeStore } from "@/shared/api/mocks/runtime";

describe("workbench dependent invalidation", () => {
  beforeEach(() => localStorage.clear());

  it("approving a new lesson plan version marks only existing PPT work stale", () => {
    const store = createMockRuntimeStore({
      storage: localStorage,
      storageKey: "workbench-invalidation-plan",
    });
    store.updateNodeState("project-a", "lesson-a", "ppt-pages", {
      status: "approved",
      title: "自定义 PPT 正文",
    });

    markLessonPlanDependentsStale(store.getState(), "project-a", "lesson-a", store);

    expect(store.getNodeState("project-a", "lesson-a", "ppt-pages")).toMatchObject({
      stale_reason: { summary: "教案已批准新版本，请更新相关课件内容" },
      status: "stale",
      title: "自定义 PPT 正文",
    });
    expect(store.getNodeState("project-a", "lesson-a", "ppt-cover")).toBeUndefined();
  });

  it("approving a new lesson division marks existing work for every saved lesson stale", () => {
    const store = createMockRuntimeStore({
      storage: localStorage,
      storageKey: "workbench-invalidation-division",
    });
    store.saveDraft(
      "project:project-a:lessons",
      [
        { id: "lesson-a", title: "第 1 课时" },
        { id: "lesson-b", title: "第 2 课时" },
      ],
      {
        nodeKey: "lesson-division",
        projectId: "project-a",
      },
    );
    store.updateNodeState("project-a", "lesson-a", "lesson-plan", {
      status: "approved",
      title: "第 1 课时教案",
    });
    store.updateNodeState("project-a", "lesson-b", "intro-options", {
      status: "approved",
      title: "第 2 课时课堂导入",
    });

    markLessonDivisionDependentsStale(store.getState(), "project-a", store);

    expect(store.getNodeState("project-a", "lesson-a", "lesson-plan")?.status).toBe("stale");
    expect(store.getNodeState("project-a", "lesson-b", "intro-options")?.status).toBe("stale");
  });

  it("can limit lesson-division invalidation to affected lesson ids", () => {
    const store = createMockRuntimeStore({
      storage: localStorage,
      storageKey: "workbench-invalidation-affected-lessons",
    });
    for (const lessonId of ["lesson-a", "lesson-b"]) {
      store.updateNodeState("project-a", lessonId, "lesson-plan", { status: "approved" });
    }

    markLessonDivisionDependentsStaleForLessons(store.getState(), "project-a", ["lesson-b"], store);

    expect(store.getNodeState("project-a", "lesson-a", "lesson-plan")?.status).toBe("approved");
    expect(store.getNodeState("project-a", "lesson-b", "lesson-plan")?.status).toBe("stale");
  });
});
