import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import { RuntimeLessonWorkbenchPage } from "@/pages/projects/RuntimeLessonWorkbenchPage";
import { useProjectEvents } from "@/shared/api/useProjectEvents";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";
const otherProjectId = "01960000-0000-7000-8000-000000000099";

function renderPage(stepKey = "lesson_plan") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[`/app/projects/${projectId}/lessons/${lessonId}/work/${stepKey}`]}
      >
        <Routes>
          <Route
            element={<RuntimeLessonWorkbenchPage />}
            path="/app/projects/:projectId/lessons/:lessonId/work/:stepKey"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeLessonWorkbenchPage", () => {
  beforeEach(() => {
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      id: projectId,
      title: "认识百分数",
    } as Awaited<ReturnType<typeof projectsApi.getProject>>);
    vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      lesson: {
        id: lessonId,
        project_id: projectId,
        lesson_key: "lesson-1",
        title: "百分数的意义",
        objective_summary: "理解百分数表示一个数是另一个数的百分之几。",
        scope_summary: "认识百分数并能正确读写。",
        estimated_minutes: 40,
        branches: [
          {
            branch_key: "lesson_plan",
            enabled: true,
            settings: {},
            workflow_status: "not_ready",
          },
          {
            branch_key: "ppt",
            enabled: true,
            settings: {},
            workflow_status: "not_ready",
          },
        ],
      },
    } as Awaited<ReturnType<typeof lessonsApi.getLesson>>);
  });

  afterEach(() => vi.restoreAllMocks());

  it("只渲染可归属当前课时的事实，不从项目节点键推断进度", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("百分数的意义");
    expect(screen.getByRole("alert", { name: "制作进度读取失败" })).toHaveTextContent(
      "这一步暂时没有可显示的制作进度",
    );
    expect(screen.getByRole("link", { name: /返回项目/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}`,
    );
    expect(screen.getByRole("link", { name: /课堂 PPT/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons/${lessonId}/work/ppt`,
    );
  });

  it("旧连字符路由与未知步骤都不会泄漏内部键", async () => {
    const first = renderPage("lesson-plan");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("教案");
    expect(screen.queryByText(/lesson-plan/)).not.toBeInTheDocument();
    first.unmount();

    renderPage("future-node-v2");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("当前步骤");
    expect(screen.queryByText(/future-node-v2/)).not.toBeInTheDocument();
  });

  it("拒绝打开不属于路由项目的课时且不启动项目事件流", async () => {
    vi.mocked(lessonsApi.getLesson).mockResolvedValueOnce({
      lesson: {
        branches: [],
        created_at: "2030-01-01T00:00:00Z",
        estimated_minutes: 40,
        id: lessonId,
        lesson_key: "lesson-1",
        lock_version: 1,
        objective_summary: "不应展示",
        position: 1,
        project_id: otherProjectId,
        scope_summary: "不应展示",
        source_division_version_id: "01960000-0000-7000-8000-000000000098",
        status: "active",
        title: "其他项目课时",
        updated_at: "2030-01-01T00:00:01Z",
      },
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "暂时无法打开课时" })).toBeVisible();
    expect(screen.queryByText("其他项目课时")).not.toBeInTheDocument();
    expect(vi.mocked(useProjectEvents)).not.toHaveBeenCalledWith(projectId);
  });
});
