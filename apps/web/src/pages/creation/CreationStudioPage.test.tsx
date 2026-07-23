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

describe("CreationStudioPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("按正式合同创建独立批次、提示词版本和生成任务", async () => {
    vi.spyOn(apiClient, "isCsrfTokenAvailable").mockReturnValue(true);
    const createBatch = vi.spyOn(creationApi, "createCreationBatch").mockResolvedValue({
      id: "batch-1",
      items: [{ id: "item-1", item_key: "item-01", status: "draft", title: "课堂图片" }],
      source_kind: "standalone",
      status: "draft",
      studio_type: "image",
      title: "课堂图片",
    });
    const savePrompt = vi.spyOn(creationApi, "saveCreationPromptVersion").mockResolvedValue({
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
    const generate = vi.spyOn(creationApi, "generateCreationItem").mockResolvedValue({
      events_url: "/generation-jobs/job-1/events/stream",
      job_id: "job-1",
      status: "queued",
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue({
      created_at: "2026-07-23T00:00:00Z",
      id: "job-1",
      job_type: "creation",
      progress_percent: 20,
      progress_message: "正在生成",
      status: "running",
      updated_at: "2026-07-23T00:00:01Z",
    });

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
    await waitFor(() => expect(savePrompt).toHaveBeenCalledTimes(1));
    expect(savePrompt.mock.calls[0]?.[0]).toMatchObject({
      input: {
        business_prompt: "画一张分数教学图",
        generation_profile: "balanced",
        reference_asset_version_ids: [],
      },
      itemId: "item-1",
    });
    await waitFor(() => expect(generate).toHaveBeenCalledTimes(1));
    expect(generate.mock.calls[0]?.[0]).toMatchObject({
      input: { candidate_count: 3, prompt_version_id: "prompt-1" },
      itemId: "item-1",
    });
    expect(await screen.findByText("创作任务")).toBeInTheDocument();
  });

  it("未知创作类型返回创作中心", () => {
    renderStudio("/app/creation/unknown");
    expect(screen.getByText("创作中心")).toBeInTheDocument();
  });
});
