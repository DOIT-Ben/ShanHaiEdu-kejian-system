import { afterEach, describe, expect, it, vi } from "vitest";
import { createDefaultMockRuntimeState } from "@/shared/api/mocks/runtime";
import {
  finalVideoMediaConfirmationKey,
  getConfirmedFinalVideoMedia,
  getPlayableFinalVideo,
  isFinalVideoMediaConfirmed,
  parsePlayableVideoMedia,
  validateSubtitleFile,
} from "@/features/workbench/lib/videoMedia";

describe("video media truth boundary", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("静态图片和没有视频类型的地址都不能冒充成片", () => {
    expect(
      parsePlayableVideoMedia({ mimeType: "image/webp", src: "/assets/keyframe.webp" }),
    ).toBeNull();
    expect(parsePlayableVideoMedia({ src: "https://cdn.example.com/final.mp4" })).toBeNull();
    expect(
      parsePlayableVideoMedia({ mimeType: "video/mp4", src: "data:video/mp4;base64,AAAA" }),
    ).toBeNull();
    expect(
      parsePlayableVideoMedia({
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleUrl: "https://cdn.example.com/final.json",
      }),
    ).toEqual({ mimeType: "video/mp4", src: "https://cdn.example.com/final.mp4" });
  });

  it("只有明确的视频地址才会解锁播放与交付", () => {
    const runtime = createDefaultMockRuntimeState();
    runtime.drafts["project:project-a:lesson:lesson-a:final-video:media"] = {
      key: "project:project-a:lesson:lesson-a:final-video:media",
      lesson_id: "lesson-a",
      node_key: "final-video",
      project_id: "project-a",
      revision: 1,
      updated_at: "2026-07-20T00:00:00Z",
      value: {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/final.mp4",
        subtitleUrl: "https://cdn.example.com/final.srt",
      },
    };

    expect(getPlayableFinalVideo(runtime, "project-a", "lesson-a")).toEqual({
      mimeType: "video/mp4",
      src: "https://cdn.example.com/final.mp4",
      subtitleSrc: "https://cdn.example.com/final.srt",
      subtitleFormat: "srt",
    });
  });

  it("只有与当前视频来源一致的确认快照才有效", () => {
    const runtime = createDefaultMockRuntimeState();
    runtime.drafts["project:project-a:lesson:lesson-a:final-video:media"] = {
      key: "project:project-a:lesson:lesson-a:final-video:media",
      lesson_id: "lesson-a",
      node_key: "final-video",
      project_id: "project-a",
      revision: 1,
      updated_at: "2026-07-20T00:00:00Z",
      value: {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/current.mp4",
        subtitleUrl: "https://cdn.example.com/current.vtt",
      },
    };
    runtime.drafts[finalVideoMediaConfirmationKey("project-a", "lesson-a")] = {
      key: finalVideoMediaConfirmationKey("project-a", "lesson-a"),
      lesson_id: "lesson-a",
      node_key: "final-video",
      project_id: "project-a",
      revision: 1,
      updated_at: "2026-07-20T00:00:00Z",
      value: {
        mimeType: "video/mp4",
        src: "https://cdn.example.com/previous.mp4",
        subtitleFormat: "vtt",
        subtitleSrc: "https://cdn.example.com/previous.vtt",
        status: "confirmed",
      },
    };

    expect(isFinalVideoMediaConfirmed(runtime, "project-a", "lesson-a")).toBe(false);

    const confirmationKey = finalVideoMediaConfirmationKey("project-a", "lesson-a");
    const confirmationDraft = runtime.drafts[confirmationKey];
    if (!confirmationDraft) throw new Error("缺少视频确认快照");
    confirmationDraft.value = {
      mimeType: "video/mp4",
      src: "https://cdn.example.com/current.mp4",
      subtitleFormat: "vtt",
      subtitleSrc: "https://cdn.example.com/previous.vtt",
      status: "confirmed",
    };

    expect(isFinalVideoMediaConfirmed(runtime, "project-a", "lesson-a")).toBe(false);

    confirmationDraft.value = {
      mimeType: "video/mp4",
      src: "https://cdn.example.com/current.mp4",
      subtitleFormat: "vtt",
      subtitleSrc: "https://cdn.example.com/current.vtt",
      status: "confirmed",
    };

    expect(isFinalVideoMediaConfirmed(runtime, "project-a", "lesson-a")).toBe(true);
    expect(getConfirmedFinalVideoMedia(runtime, "project-a", "lesson-a")).toBeNull();

    runtime.nodeStates["project-a:lesson-a:final-video"] = {
      id: "node-final-video",
      lesson_id: "lesson-a",
      node_key: "final-video",
      project_id: "project-a",
      revision: 1,
      stale_reason: null,
      status: "approved",
      title: "生成课堂导入视频",
      updated_at: "2026-07-20T00:00:00Z",
    };
    expect(getConfirmedFinalVideoMedia(runtime, "project-a", "lesson-a")).toMatchObject({
      src: "https://cdn.example.com/current.mp4",
      subtitleFormat: "vtt",
      subtitleSrc: "https://cdn.example.com/current.vtt",
    });
  });

  it("字幕校验拒绝错误 MIME 和伪字幕正文", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response("WEBVTT\n\n00:00.000 --> 00:01.000\n课堂导入", {
          headers: { "content-type": "video/mp4" },
          status: 200,
        }),
      )
      .mockResolvedValueOnce(
        new Response("这不是字幕文件", {
          headers: { "content-type": "text/vtt" },
          status: 200,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(validateSubtitleFile("https://cdn.example.com/wrong.vtt", "vtt")).resolves.toBe(
      false,
    );
    await expect(validateSubtitleFile("https://cdn.example.com/fake.vtt", "vtt")).resolves.toBe(
      false,
    );
  });
});
