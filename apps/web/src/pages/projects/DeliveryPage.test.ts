import { beforeEach, describe, expect, it } from "vitest";
import {
  buildDeliveryRequirements,
  createDeliveryFingerprint,
} from "@/pages/projects/DeliveryPage";
import { createMockRuntimeStore, type MockRuntimeStore } from "@/shared/api/mocks/runtime";
import { saveMockResult } from "@/shared/api/mocks/savedResults";
import { demoLessonId, demoProjectId, lessons } from "@/shared/data/mockData";

describe("delivery requirements", () => {
  let store: MockRuntimeStore;

  beforeEach(() => {
    localStorage.clear();
    store = createMockRuntimeStore({ storage: localStorage });
  });

  it("requires every lesson plan and only enabled optional branches", () => {
    const secondLesson = lessons[1];
    expect(secondLesson).toBeDefined();
    if (!secondLesson) return;
    store.saveDraft(`project:${demoProjectId}:lessons`, lessons, { projectId: demoProjectId });
    store.updateNodeState(demoProjectId, demoLessonId, "lesson-plan", { status: "approved" });
    store.updateNodeState(demoProjectId, demoLessonId, "ppt-pages", { status: "approved" });
    store.updateNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });

    const requirements = buildDeliveryRequirements(store.getState(), demoProjectId);

    expect(requirements).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ key: `${demoLessonId}:lesson-plan`, status: "approved" }),
        expect.objectContaining({ key: `${demoLessonId}:ppt-pages`, status: "approved" }),
        expect.objectContaining({
          key: `${demoLessonId}:final-video`,
          status: "not_ready",
        }),
        expect.objectContaining({ key: `${secondLesson.id}:lesson-plan`, status: "draft" }),
      ]),
    );
    expect(requirements.some((item) => item.key === `${secondLesson.id}:ppt-pages`)).toBe(false);
    expect(requirements.some((item) => item.key === `${secondLesson.id}:final-video`)).toBe(false);
    expect(requirements.every((item) => item.status === "approved")).toBe(false);
    expect(
      requirements.find((item) => item.key === `${demoLessonId}:final-video`)?.media,
    ).toBeUndefined();
  });

  it("只有明确的视频地址才允许进入交付", () => {
    store.updateNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });
    store.saveDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:final-video:media`,
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleSrc: "https://cdn.example.com/final.srt",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    const requirement = buildDeliveryRequirements(store.getState(), demoProjectId).find(
      (item) => item.key === `${demoLessonId}:final-video`,
    );

    expect(requirement).toMatchObject({
      media: {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleSrc: "https://cdn.example.com/final.srt",
      },
      status: "approved",
    });
  });

  it("changes the delivery fingerprint when the current saved result changes", () => {
    const before = createDeliveryFingerprint(store.getState(), demoProjectId);
    saveMockResult(
      {
        lessonLabel: "第 1 课时",
        projectId: demoProjectId,
        replaceMode: "replace",
        resultId: "delivery-result-1",
        slotKey: "ppt.page-3.hero",
        slotLabel: "第 1 课时 · PPT 第 3 页主视觉",
        title: "交付图片",
        type: "image",
      },
      store,
    );
    const after = createDeliveryFingerprint(store.getState(), demoProjectId);

    expect(after).not.toBe(before);
  });
});
