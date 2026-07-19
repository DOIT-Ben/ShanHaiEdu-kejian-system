import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import { RuntimeProjectSetupPage } from "@/pages/projects/RuntimeProjectSetupPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";

vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const jobId = "01960000-0000-7000-8000-000000000002";
const runningJob: GenerationJobDto = {
  created_at: "2030-01-01T00:00:00Z",
  id: jobId,
  job_type: "textbook.parse",
  progress_message: "正在整理教材内容",
  progress_percent: 42,
  project_id: projectId,
  status: "running",
  updated_at: "2030-01-01T00:00:01Z",
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/app/projects/${projectId}/setup?jobId=${jobId}`]}>
        <Routes>
          <Route path="/app/projects/:projectId/setup" element={<RuntimeProjectSetupPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeProjectSetupPage", () => {
  beforeEach(() => {
    configureCsrfTokenProvider(() => "csrf-test-token");
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      title: "认识百分数",
    } as Awaited<ReturnType<typeof projectsApi.getProject>>);
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(runningJob);
  });

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("取消失败后给出可理解的提示并允许再次取消", async () => {
    const user = userEvent.setup();
    const cancelJob = vi
      .spyOn(jobsApi, "cancelGenerationJob")
      .mockRejectedValueOnce(new Error("internal cancellation failure"))
      .mockResolvedValue({ ...runningJob, status: "cancel_requested" });
    renderPage();

    await user.click(await screen.findByRole("button", { name: "取消任务" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("任务还没有取消");
    expect(screen.getByRole("alert")).not.toHaveTextContent("internal cancellation failure");
    const retryButton = screen.getByRole("button", { name: "重试取消" });
    expect(retryButton).toBeEnabled();

    await user.click(retryButton);
    await waitFor(() => expect(cancelJob).toHaveBeenCalledTimes(2));
  });

  it("向辅助技术公开教材处理进度", async () => {
    renderPage();

    const progress = await screen.findByRole("progressbar", { name: "教材处理进度 42%" });
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
    expect(progress).toHaveAttribute("aria-valuenow", "42");
  });
});
