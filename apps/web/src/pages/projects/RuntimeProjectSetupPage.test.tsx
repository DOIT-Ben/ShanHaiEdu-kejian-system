import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import { RuntimeProjectSetupPage } from "@/pages/projects/RuntimeProjectSetupPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";
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
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v0"',
      lessons: [],
      lockVersion: 0,
    });
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
    expect(cancelJob.mock.calls[0]?.[0].idempotencyKey).toBe(
      cancelJob.mock.calls[1]?.[0].idempotencyKey,
    );
  });

  it("取消响应丢失后以 REST 对账清除过期错误", async () => {
    vi.mocked(jobsApi.getGenerationJob)
      .mockResolvedValueOnce(runningJob)
      .mockResolvedValue({
        ...runningJob,
        progress_message: "正在取消任务",
        status: "cancel_requested",
      });
    vi.spyOn(jobsApi, "cancelGenerationJob").mockRejectedValue(new Error("response lost"));
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: "取消任务" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("任务还没有取消");

    await user.click(screen.getByRole("button", { name: "刷新" }));
    await screen.findByText("正在取消任务");
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "重试取消" })).not.toBeInTheDocument();
  });

  it("向辅助技术公开教材处理进度", async () => {
    renderPage();

    const progress = await screen.findByRole("progressbar", { name: "教材处理进度 42%" });
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
    expect(progress).toHaveAttribute("aria-valuenow", "42");
  });

  it("教材任务进入终态后停止事件流", async () => {
    vi.mocked(jobsApi.getGenerationJob).mockResolvedValueOnce({
      ...runningJob,
      progress_message: "教材整理完成",
      progress_percent: 100,
      status: "succeeded",
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "教材已经准备好" })).toBeVisible();
    expect(vi.mocked(useJobEvents)).not.toHaveBeenCalledWith(jobId, projectId);
  });

  it("教材解析成功但服务端没有课时时明确阻断后续生成", async () => {
    vi.mocked(jobsApi.getGenerationJob).mockResolvedValueOnce({
      ...runningJob,
      progress_message: "教材整理完成",
      progress_percent: 100,
      status: "succeeded",
    });
    vi.mocked(lessonsApi.listProjectLessons).mockResolvedValueOnce({
      etag: '"lessons-v0"',
      lessons: [],
      lockVersion: 0,
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "课时尚未建立" })).toBeVisible();
    expect(screen.getByText(/课时创建和教案生成暂不可用/)).toBeVisible();
    expect(screen.queryByText(/课时建议还在准备/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回项目" })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}`,
    );
    expect(screen.queryByRole("link", { name: "查看课时" })).not.toBeInTheDocument();
  });

  it("教材解析成功且服务端已有课时时进入课时页面", async () => {
    vi.mocked(jobsApi.getGenerationJob).mockResolvedValueOnce({
      ...runningJob,
      progress_message: "教材整理完成",
      progress_percent: 100,
      status: "succeeded",
    });
    vi.mocked(lessonsApi.listProjectLessons).mockResolvedValueOnce({
      etag: '"lessons-v1"',
      lessons: [{ id: "lesson-1" } as lessonsApi.LessonDto],
      lockVersion: 1,
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "课时已经可以核对" })).toBeVisible();
    expect(screen.getByText("项目中已经保存 1 个课时，可以进入课时页核对和编辑。")).toBeVisible();
    expect(screen.getByRole("link", { name: "查看课时" })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons`,
    );
    expect(screen.queryByText(/课时创建和教案生成暂不可用/)).not.toBeInTheDocument();
  });

  it.each([null, "01960000-0000-7000-8000-000000000099"])(
    "拒绝归属为 %s 的教材任务且不允许取消或启动事件流",
    async (jobProjectId) => {
      vi.mocked(jobsApi.getGenerationJob).mockResolvedValueOnce({
        ...runningJob,
        project_id: jobProjectId,
      });
      const cancelJob = vi.spyOn(jobsApi, "cancelGenerationJob");

      renderPage();

      expect(await screen.findByRole("heading", { name: "教材进度暂时无法打开" })).toBeVisible();
      expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();
      expect(cancelJob).not.toHaveBeenCalled();
      expect(vi.mocked(useJobEvents)).not.toHaveBeenCalledWith(jobId, projectId);
    },
  );
});
