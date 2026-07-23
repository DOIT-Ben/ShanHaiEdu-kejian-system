import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as creationApi from "@/features/creation-studio/api/creationApi";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import { CreationStudioPage } from "@/pages/creation/CreationStudioPage";
import * as apiClient from "@/shared/api/client";

vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

function renderStudio(path = "/app/creation/images") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route element={<CreationStudioPage />} path="/app/creation/:studioPath" />
            <Route element={<p>创作中心</p>} path="/app/creation" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

function mockAcceptedCreation() {
  vi.spyOn(apiClient, "isCsrfTokenAvailable").mockReturnValue(true);
  vi.spyOn(creationApi, "createCreationBatch").mockResolvedValue({
    id: "batch-1",
    items: [{ id: "item-1", item_key: "item-01", status: "draft", title: "课堂图片" }],
    source_kind: "standalone",
    status: "draft",
    studio_type: "image",
    title: "课堂图片",
  });
  vi.spyOn(creationApi, "saveCreationPromptVersion").mockResolvedValue({
    business_prompt: "画一张分数教学图",
    content_hash: "hash",
    created_at: "2026-07-23T00:00:00Z",
    creation_item_id: "item-1",
    generation_profile: "balanced",
    id: "prompt-1",
    output_spec: {},
    reference_asset_version_ids: [],
    version_no: 1,
  });
  return vi.spyOn(creationApi, "generateCreationItem").mockResolvedValue({
    events_url: "/generation-jobs/job-1/events/stream",
    job_id: "job-1",
    status: "queued",
  });
}

function startCreation() {
  renderStudio();
  fireEvent.change(screen.getByLabelText("描述你想创作的图片"), {
    target: { value: "画一张分数教学图" },
  });
  fireEvent.click(screen.getByRole("button", { name: "开始创作图片" }));
}

describe("CreationStudioPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("正式批次不含创作条目时明确阻断且不伪造生成链", async () => {
    vi.spyOn(apiClient, "isCsrfTokenAvailable").mockReturnValue(true);
    const createBatch = vi.spyOn(creationApi, "createCreationBatch").mockResolvedValue({
      id: "batch-1",
      items: [],
      source_kind: "standalone",
      status: "draft",
      studio_type: "image",
      title: "课堂图片",
    });
    const savePrompt = vi.spyOn(creationApi, "saveCreationPromptVersion");
    const generate = vi.spyOn(creationApi, "generateCreationItem");

    renderStudio();
    fireEvent.change(screen.getByLabelText("描述你想创作的图片"), {
      target: { value: "画一张分数教学图" },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始创作图片" }));

    await waitFor(() => expect(createBatch).toHaveBeenCalledTimes(1));
    expect(createBatch.mock.calls[0]?.[0].input).toEqual({
      source_kind: "standalone",
      studio_type: "image",
      title: "画一张教学图片",
    });
    expect(await screen.findByText("独立创作暂时无法生成作品，请稍后再试。")).toBeInTheDocument();
    expect(savePrompt).not.toHaveBeenCalled();
    expect(generate).not.toHaveBeenCalled();
    expect(screen.queryByText("创作任务")).not.toBeInTheDocument();
  });

  it("已有生成任务但首次读取失败时保持锁定，避免重复创建任务", async () => {
    const generate = mockAcceptedCreation();
    vi.spyOn(jobsApi, "getGenerationJob").mockRejectedValue(new Error("network unavailable"));

    startCreation();

    expect(await screen.findByText("任务状态暂时无法读取，请刷新后重试。")).toBeInTheDocument();
    const generateButton = screen.getByRole("button", { name: "等待创作" });
    expect(generateButton).toBeDisabled();
    fireEvent.click(generateButton);
    expect(generate).toHaveBeenCalledTimes(1);
  });

  it("保留运行快照的刷新失败只显示读取错误，不解锁重复生成", async () => {
    const generate = mockAcceptedCreation();
    vi.spyOn(jobsApi, "getGenerationJob")
      .mockResolvedValueOnce({
        created_at: "2026-07-23T00:00:00Z",
        id: "job-1",
        job_type: "creation",
        progress_percent: 20,
        progress_message: "正在生成",
        status: "running",
        updated_at: "2026-07-23T00:00:01Z",
      })
      .mockRejectedValueOnce(new Error("network unavailable"));

    startCreation();

    expect(await screen.findByText("正在生成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));
    expect(await screen.findByText("任务状态暂时无法读取，请刷新后重试。")).toBeInTheDocument();
    const generateButton = screen.getByRole("button", { name: "正在创作" });
    expect(generateButton).toBeDisabled();
    fireEvent.click(generateButton);
    expect(generate).toHaveBeenCalledTimes(1);
  });

  it("未知创作类型返回创作中心", () => {
    renderStudio("/app/creation/unknown");
    expect(screen.getByText("创作中心")).toBeInTheDocument();
  });
});
