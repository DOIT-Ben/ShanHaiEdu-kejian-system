import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as videoApi from "@/features/video-golden-slice/api/videoGoldenSliceApi";
import { VideoGoldenSliceWorkflowPanel } from "@/features/video-golden-slice/components/VideoGoldenSliceWorkflowPanel";
import { configureCsrfTokenProvider } from "@/shared/api/client";

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";
const keyframeId = "01960000-0000-7000-8000-000000000003";
const resultId = "01960000-0000-7000-8000-000000000004";
const adoptionId = "01960000-0000-7000-8000-000000000005";

function slice(
  candidate: Awaited<ReturnType<typeof videoApi.getVideoGoldenSlice>>["candidate"] = null,
): Awaited<ReturnType<typeof videoApi.getVideoGoldenSlice>> {
  return {
    candidate,
    intro_artifact_version_id: "01960000-0000-7000-8000-000000000006",
    intro_selection_id: "01960000-0000-7000-8000-000000000007",
    job: null,
    keyframe_file_asset_version_id: keyframeId,
    keyframe_slot_key: "lesson.01.image.keyframe",
    lesson_unit_id: lessonId,
    project_id: projectId,
  };
}

function candidate(adopted = false, saved = false) {
  return {
    adoption_id: adopted ? adoptionId : null,
    byte_size: 4096,
    duration_ms: 6000,
    file_asset_version_id: "01960000-0000-7000-8000-000000000008",
    mime_type: "video/mp4" as const,
    playback_url: `/api/v2/projects/${projectId}/lessons/${lessonId}/video/results/${resultId}/content`,
    result_id: resultId,
    saved_binding_id: saved ? "01960000-0000-7000-8000-000000000009" : null,
    sha256: "a".repeat(64),
  };
}

function renderPanel() {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <VideoGoldenSliceWorkflowPanel lessonId={lessonId} projectId={projectId} />
    </QueryClientProvider>,
  );
}

describe("VideoGoldenSliceWorkflowPanel", () => {
  beforeEach(() => configureCsrfTokenProvider(() => "test-csrf-token"));
  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("使用服务端返回的 exact 关键帧启动唯一 6 秒生成任务", async () => {
    const user = userEvent.setup();
    vi.spyOn(videoApi, "getVideoGoldenSlice").mockResolvedValue(slice());
    const start = vi.spyOn(videoApi, "startVideoGeneration").mockResolvedValue({
      events_url: "/api/v2/generation-jobs/job-1/events/stream",
      job_id: "01960000-0000-7000-8000-000000000010",
      status: "queued",
    });
    renderPanel();

    await user.click(await screen.findByRole("button", { name: "生成 6 秒短片" }));

    expect(start).toHaveBeenCalledTimes(1);
    const request = start.mock.calls[0]?.[0];
    expect(typeof request?.idempotencyKey).toBe("string");
    expect(request?.keyframeFileAssetVersionId).toBe(keyframeId);
    expect(request?.lessonId).toBe(lessonId);
    expect(request?.projectId).toBe(projectId);
  });

  it("关键帧缺失时显示真实状态并禁止启动生成", async () => {
    vi.spyOn(videoApi, "getVideoGoldenSlice").mockResolvedValue({
      ...slice(),
      keyframe_file_asset_version_id: null,
      keyframe_slot_key: null,
    });
    renderPanel();

    expect(await screen.findByText("正式关键帧尚未绑定")).toBeVisible();
    expect(screen.queryByText("正式关键帧已绑定")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成 6 秒短片" })).toBeDisabled();
  });

  it("播放 exact MP4，并按候选采用后写回课时槽位", async () => {
    const user = userEvent.setup();
    vi.spyOn(videoApi, "getVideoGoldenSlice")
      .mockResolvedValueOnce(slice(candidate()))
      .mockResolvedValue(slice(candidate(true)));
    const adopt = vi.spyOn(videoApi, "adoptVideoResult").mockResolvedValue({
      adoption_mode: "teacher",
      adopted_at: "2030-01-01T00:00:00Z",
      creation_item_id: "01960000-0000-7000-8000-000000000012",
      generation_result_id: resultId,
      id: adoptionId,
      reason: "采用这段课堂导入短片",
    });
    const save = vi.spyOn(videoApi, "saveVideoAdoption").mockResolvedValue({
      adoption_id: adoptionId,
      binding_id: "01960000-0000-7000-8000-000000000014",
      idempotent_replay: false,
      operation_id: "01960000-0000-7000-8000-000000000013",
      status: "completed",
      target_project_id: projectId,
      target_slot_key: "lesson.01.video.intro.selected",
    });
    renderPanel();

    const player = await screen.findByLabelText("6 秒课堂导入短片");
    expect(player).toHaveAttribute("src", candidate().playback_url);
    await user.click(screen.getByRole("button", { name: "采用这段短片" }));
    expect(adopt).toHaveBeenCalledWith(expect.objectContaining({ resultId }));
    await user.click(await screen.findByRole("button", { name: "保存到当前课时" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ adoptionId }));
  });

  it("刷新后恢复已保存状态，不重复显示写入按钮", async () => {
    vi.spyOn(videoApi, "getVideoGoldenSlice").mockResolvedValue(slice(candidate(true, true)));
    renderPanel();

    expect(await screen.findByText("已保存到当前课时")).toBeVisible();
    expect(screen.queryByRole("button", { name: "采用这段短片" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存到当前课时" })).not.toBeInTheDocument();
  });
});
