import { beforeEach, describe, expect, it } from "vitest";
import { buildCreationResultId } from "@/features/creation-studio/model";
import { createMockRuntimeStore } from "@/shared/api/mocks/runtime";
import {
  listMockSavedResultHistory,
  listMockSavedResults,
  saveMockResult,
} from "@/shared/api/mocks/savedResults";

describe("mock saved results", () => {
  beforeEach(() => localStorage.clear());

  it("keeps different creation results in the same project without overwriting them", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    const projectId = store.getState().projects[0]?.id;
    expect(projectId).toBeTruthy();
    if (!projectId) return;

    saveMockResult(
      {
        lessonLabel: "独立创作",
        projectId,
        replaceMode: "replace",
        resultId: "image-candidate-1",
        slotKey: "project.shared-images",
        slotLabel: "项目通用教学图片",
        title: "果汁标签图片",
        type: "image",
      },
      store,
    );
    saveMockResult(
      {
        lessonLabel: "独立创作",
        projectId,
        replaceMode: "replace",
        resultId: "video-candidate-1",
        slotKey: "video.shot-2",
        slotLabel: "第 1 课时 · 视频镜头 2",
        title: "果汁标签视频",
        type: "video",
      },
      store,
    );

    expect(listMockSavedResults(store.getState(), projectId)).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ resultId: "image-candidate-1", type: "image" }),
        expect.objectContaining({ resultId: "video-candidate-1", type: "video" }),
      ]),
    );
    expect(listMockSavedResults(store.getState(), projectId)).toHaveLength(2);
  });

  it("replaces one slot atomically, archives the previous version, and invalidates delivery", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    const projectId = store.getState().projects[0]?.id;
    expect(projectId).toBeTruthy();
    if (!projectId) return;

    const first = saveMockResult(
      {
        lessonLabel: "第 1 课时",
        preview: { candidate: 0, generation: 1, ratio: "1:1" },
        projectId,
        replaceMode: "replace",
        resultId: "image-candidate-1",
        slotKey: "ppt.page-3.hero",
        slotLabel: "第 1 课时 · PPT 第 3 页主视觉",
        title: "果汁标签图片",
        type: "image",
      },
      store,
    );
    store.saveDraft(
      `project:${projectId}:delivery-package`,
      { fingerprint: "before-replacement", status: "ready" },
      { projectId },
    );
    let notifications = 0;
    const unsubscribe = store.subscribe(() => {
      notifications += 1;
    });

    const current = saveMockResult(
      {
        lessonLabel: "第 1 课时",
        preview: { candidate: 1, generation: 2, ratio: "4:3" },
        projectId,
        replaceMode: "replace",
        resultId: "image-candidate-2",
        slotKey: "ppt.page-3.hero",
        slotLabel: "第 1 课时 · PPT 第 3 页主视觉",
        title: "果汁标签图片（调整后）",
        type: "image",
      },
      store,
    );
    unsubscribe();

    expect(notifications).toBe(1);
    expect(listMockSavedResults(store.getState(), projectId)).toEqual([
      expect.objectContaining({ resultId: "image-candidate-2", version: 2 }),
    ]);
    expect(listMockSavedResultHistory(store.getState(), projectId, "ppt.page-3.hero")).toEqual([
      expect.objectContaining({
        id: current.id,
        preview: { candidate: 1, generation: 2, ratio: "4:3" },
        version: 2,
      }),
      expect.objectContaining({
        id: first.id,
        preview: { candidate: 0, generation: 1, ratio: "1:1" },
        version: 1,
      }),
    ]);
    expect(store.getState().drafts[`project:${projectId}:delivery-package`]?.value).toMatchObject({
      status: "stale",
    });
  });

  it("保存同一候选的新创作轮次时生成新版本，而不是复用旧结果", () => {
    const store = createMockRuntimeStore({ storage: localStorage });
    const projectId = store.getState().projects[0]?.id;
    expect(projectId).toBeTruthy();
    if (!projectId) return;

    saveMockResult(
      {
        lessonLabel: "独立创作",
        projectId,
        replaceMode: "replace",
        resultId: buildCreationResultId("image", 1, 0),
        slotKey: "project.shared-images",
        slotLabel: "项目通用教学图片",
        title: "第一轮图片",
        type: "image",
      },
      store,
    );
    const current = saveMockResult(
      {
        lessonLabel: "独立创作",
        projectId,
        replaceMode: "replace",
        resultId: buildCreationResultId("image", 2, 0),
        slotKey: "project.shared-images",
        slotLabel: "项目通用教学图片",
        title: "第二轮图片",
        type: "image",
      },
      store,
    );

    expect(current).toMatchObject({
      resultId: "creation-image-generation-2-candidate-1",
      title: "第二轮图片",
      version: 2,
    });
    expect(
      listMockSavedResultHistory(store.getState(), projectId, "project.shared-images"),
    ).toHaveLength(2);
  });
});
