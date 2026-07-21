import { beforeEach, describe, expect, it } from "vitest";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";
import { createDefaultMockRuntimeState, createMockRuntimeStore } from "@/shared/api/mocks/runtime";
import {
  getPreviousWorkbenchStepKey,
  getWorkbenchStepBlocker,
  getWorkbenchStepStatus,
} from "@/features/workbench/lib/stepAccess";

describe("workbench step access", () => {
  beforeEach(() => localStorage.clear());

  it("requires a ready textbook before approving the lesson division", () => {
    const seed = createDefaultMockRuntimeState();
    seed.textbookFiles[demoProjectId] =
      seed.textbookFiles[demoProjectId]?.map((file) => ({
        ...file,
        status: "uploaded",
      })) ?? [];
    const store = createMockRuntimeStore({ storage: null, seed });

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "lesson-division"),
    ).toMatchObject({ dependencyKey: "materials", toStep: "materials" });
  });

  it("requires approved lesson division for lesson plans and intro options", () => {
    const seed = createDefaultMockRuntimeState();
    const nodeStates = Object.fromEntries(
      Object.entries(seed.nodeStates).filter(
        ([key]) => key !== `${demoProjectId}:*:lesson-division`,
      ),
    );
    const store = createMockRuntimeStore({
      seed: { ...seed, nodeStates },
      storage: localStorage,
      storageKey: "workbench-step-access",
    });

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "lesson-plan"),
    ).toMatchObject({ dependencyKey: "lesson-division" });
    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "intro-options"),
    ).toMatchObject({ dependencyKey: "lesson-division" });

    store.updateNodeState(demoProjectId, null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "lesson-plan"),
    ).toBeNull();
    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "intro-options"),
    ).toBeNull();
  });

  it("does not trust an approved lesson-division node without its approved snapshot", () => {
    const seed = createDefaultMockRuntimeState();
    const approvedKey = `project:${demoProjectId}:lessons-approved`;
    seed.drafts = Object.fromEntries(
      Object.entries(seed.drafts).filter(([key]) => key !== approvedKey),
    );
    const store = createMockRuntimeStore({ seed, storage: null });

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "lesson-plan"),
    ).toMatchObject({ dependencyKey: "lesson-division" });
    expect(
      getWorkbenchStepStatus(store.getState(), demoProjectId, demoLessonId, "lesson-division"),
    ).toBe("review_required");
  });

  it("keeps video work locked until the regenerated intro preview is adopted", () => {
    const store = createMockRuntimeStore({
      storage: localStorage,
      storageKey: "workbench-step-access-intro",
    });
    const optionKey = "INTRO-APP-01";
    store.saveDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:intro-options`,
      {
        adoptedKey: optionKey,
        adoptedRevision: 0,
        previewKey: optionKey,
        previewRevision: 1,
        revisions: { [optionKey]: 1 },
      },
      { lessonId: demoLessonId, nodeKey: "intro-options", projectId: demoProjectId },
    );
    store.updateNodeState(demoProjectId, demoLessonId, "intro-options", {
      status: "approved",
      title: "选择课堂导入",
    });

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "master-script"),
    ).toMatchObject({ dependencyKey: "intro-options" });

    store.saveDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:intro-options`,
      {
        adoptedKey: optionKey,
        adoptedRevision: 1,
        previewKey: optionKey,
        previewRevision: 1,
        revisions: { [optionKey]: 1 },
      },
      { lessonId: demoLessonId, nodeKey: "intro-options", projectId: demoProjectId },
    );

    expect(
      getWorkbenchStepBlocker(store.getState(), demoProjectId, demoLessonId, "master-script"),
    ).toBeNull();
  });

  it("returns to the real dependency within PPT and video branches", () => {
    expect(getPreviousWorkbenchStepKey("materials")).toBeNull();
    expect(getPreviousWorkbenchStepKey("ppt-pages")).toBe("ppt-cover");
    expect(getPreviousWorkbenchStepKey("master-script")).toBe("intro-options");
    expect(getPreviousWorkbenchStepKey("rough-storyboard")).toBe("master-script");
  });
});
