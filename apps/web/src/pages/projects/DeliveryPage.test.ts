import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildDeliveryRequirements,
  createDeliveryFingerprint,
  DeliveryPage,
} from "@/pages/projects/DeliveryPage";
import {
  createMockRuntimeStore,
  getMockRuntimeState,
  resetMockRuntime,
  saveMockDraft,
  type MockRuntimeStore,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";
import { saveMockResult } from "@/shared/api/mocks/savedResults";
import { finalVideoMediaConfirmationKey } from "@/features/workbench/lib/videoMedia";
import { downloadRemoteFile } from "@/shared/lib/downloadRemoteFile";
import { demoLessonId, demoProjectId, lessons } from "@/shared/data/mockData";

vi.mock("@/shared/lib/downloadRemoteFile", () => ({
  downloadRemoteFile: vi.fn(),
}));

const mockDownloadRemoteFile = vi.mocked(downloadRemoteFile);

describe("delivery requirements", () => {
  let store: MockRuntimeStore;

  beforeEach(() => {
    localStorage.clear();
    resetMockRuntime();
    mockDownloadRemoteFile.mockReset();
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

  it("只有浏览器确认过且来源未变化的视频才允许进入交付", () => {
    store.updateNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });
    store.saveDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:final-video:media`,
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleSrc: "https://cdn.example.com/final.srt",
        subtitleFormat: "srt",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    let requirement = buildDeliveryRequirements(store.getState(), demoProjectId).find(
      (item) => item.key === `${demoLessonId}:final-video`,
    );

    expect(requirement).toMatchObject({ status: "not_ready" });
    expect(requirement?.media).toBeUndefined();

    store.saveDraft(
      finalVideoMediaConfirmationKey(demoProjectId, demoLessonId),
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/previous.mp4",
        status: "confirmed",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    requirement = buildDeliveryRequirements(store.getState(), demoProjectId).find(
      (item) => item.key === `${demoLessonId}:final-video`,
    );
    expect(requirement).toMatchObject({ status: "not_ready" });
    expect(requirement?.media).toBeUndefined();

    store.saveDraft(
      finalVideoMediaConfirmationKey(demoProjectId, demoLessonId),
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleFormat: "srt",
        subtitleSrc: "https://cdn.example.com/final.srt",
        status: "confirmed",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    requirement = buildDeliveryRequirements(store.getState(), demoProjectId).find(
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

  it("字幕来源或格式变化会让已准备交付失效", () => {
    store.updateNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });
    const mediaKey = `project:${demoProjectId}:lesson:${demoLessonId}:final-video:media`;
    store.saveDraft(
      mediaKey,
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleMimeType: "text/vtt",
        subtitleUrl: "https://cdn.example.com/first.vtt",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );
    store.saveDraft(
      finalVideoMediaConfirmationKey(demoProjectId, demoLessonId),
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleFormat: "vtt",
        subtitleSrc: "https://cdn.example.com/first.vtt",
        status: "confirmed",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    const before = createDeliveryFingerprint(store.getState(), demoProjectId);
    store.saveDraft(
      mediaKey,
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleMimeType: "application/x-subrip",
        subtitleUrl: "https://cdn.example.com/second.srt",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    const after = createDeliveryFingerprint(store.getState(), demoProjectId);
    const requirement = buildDeliveryRequirements(store.getState(), demoProjectId).find(
      (item) => item.key === `${demoLessonId}:final-video`,
    );
    expect(after).not.toBe(before);
    expect(requirement).toMatchObject({ status: "not_ready" });
    expect(requirement?.media).toBeUndefined();
  });

  it("VTT 字幕在交付清单中保留真实扩展名", () => {
    updateMockNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });
    saveMockDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:final-video:media`,
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleMimeType: "text/vtt",
        subtitleUrl: "https://cdn.example.com/final.vtt",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );
    saveMockDraft(
      finalVideoMediaConfirmationKey(demoProjectId, demoLessonId),
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleFormat: "vtt",
        subtitleSrc: "https://cdn.example.com/final.vtt",
        status: "confirmed",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );

    render(
      createElement(
        MemoryRouter,
        { initialEntries: [`/projects/${demoProjectId}/delivery`] },
        createElement(
          Routes,
          null,
          createElement(Route, {
            element: createElement(DeliveryPage),
            path: "/projects/:projectId/delivery",
          }),
        ),
      ),
    );

    expect(screen.getByText(/_课堂导入字幕\.vtt$/)).toBeInTheDocument();
    expect(screen.queryByText(/_课堂导入字幕\.srt$/)).not.toBeInTheDocument();
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

  it("交付页下载失败后保留同一文件的重试入口", async () => {
    const secondLesson = lessons[1];
    expect(secondLesson).toBeDefined();
    if (!secondLesson) return;
    updateMockNodeState(demoProjectId, demoLessonId, "lesson-plan", { status: "approved" });
    updateMockNodeState(demoProjectId, demoLessonId, "ppt-pages", { status: "approved" });
    updateMockNodeState(demoProjectId, demoLessonId, "final-video", { status: "approved" });
    updateMockNodeState(demoProjectId, secondLesson.id, "lesson-plan", { status: "approved" });
    saveMockDraft(
      `project:${demoProjectId}:lesson:${demoLessonId}:final-video:media`,
      { mimeType: "video/mp4", src: "https://cdn.example.com/final.mp4" },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );
    saveMockDraft(
      finalVideoMediaConfirmationKey(demoProjectId, demoLessonId),
      {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        status: "confirmed",
      },
      { lessonId: demoLessonId, nodeKey: "final-video", projectId: demoProjectId },
    );
    const fingerprint = createDeliveryFingerprint(getMockRuntimeState(), demoProjectId);
    saveMockDraft(
      `project:${demoProjectId}:delivery-package`,
      { fingerprint, status: "ready" },
      { projectId: demoProjectId },
    );
    mockDownloadRemoteFile.mockRejectedValueOnce(new Error("cors"));
    mockDownloadRemoteFile.mockResolvedValueOnce();

    render(
      createElement(
        MemoryRouter,
        { initialEntries: [`/projects/${demoProjectId}/delivery`] },
        createElement(
          Routes,
          null,
          createElement(Route, {
            element: createElement(DeliveryPage),
            path: "/projects/:projectId/delivery",
          }),
        ),
      ),
    );

    expect(screen.getByText("教学内容与当前可用媒体检查 · 当前说明")).toBeInTheDocument();
    expect(screen.queryByText(/声音与字幕检查/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "下载文件" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("暂时无法下载");
    fireEvent.click(screen.getByRole("button", { name: "重新下载" }));

    await waitFor(() => expect(mockDownloadRemoteFile).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("status")).toHaveTextContent("已开始下载");
  });
});
