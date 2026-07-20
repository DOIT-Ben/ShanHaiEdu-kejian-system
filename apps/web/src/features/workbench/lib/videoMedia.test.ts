import { describe, expect, it } from "vitest";
import { createDefaultMockRuntimeState } from "@/shared/api/mocks/runtime";
import {
  finalVideoMediaConfirmationKey,
  getPlayableFinalVideo,
  isFinalVideoMediaConfirmed,
  parsePlayableVideoMedia,
} from "@/features/workbench/lib/videoMedia";

describe("video media truth boundary", () => {
  it("静态图片和没有视频类型的地址都不能冒充成片", () => {
    expect(
      parsePlayableVideoMedia({ mimeType: "image/webp", src: "/assets/keyframe.webp" }),
    ).toBeNull();
    expect(parsePlayableVideoMedia({ src: "https://cdn.example.com/final.mp4" })).toBeNull();
    expect(
      parsePlayableVideoMedia({ mimeType: "video/mp4", src: "data:video/mp4;base64,AAAA" }),
    ).toBeNull();
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
      value: { mimeType: "video/mp4", src: "https://cdn.example.com/current.mp4" },
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
      status: "confirmed",
    };

    expect(isFinalVideoMediaConfirmed(runtime, "project-a", "lesson-a")).toBe(true);
  });
});
