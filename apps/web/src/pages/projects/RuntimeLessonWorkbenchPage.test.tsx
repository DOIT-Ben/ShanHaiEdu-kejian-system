import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import * as workflowApi from "@/features/workflow/api/workflowApi";
import { RuntimeLessonWorkbenchPage } from "@/pages/projects/RuntimeLessonWorkbenchPage";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[`/app/projects/${projectId}/lessons/${lessonId}/work/lesson_plan`]}
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
    vi.spyOn(workflowApi, "getProjectWorkflow").mockResolvedValue({
      project: { id: projectId },
      lessons: [],
      node_runs: [
        {
          id: "01960000-0000-7000-8000-000000000003",
          node_key: "lesson_plan",
          status: "running",
          title: "生成教案",
        },
      ],
    } as unknown as Awaited<ReturnType<typeof workflowApi.getProjectWorkflow>>);
  });

  afterEach(() => vi.restoreAllMocks());

  it("从真实项目、课时和工作流数据渲染课时工作台", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("百分数的意义");
    expect(screen.getByText("生成教案")).toBeVisible();
    expect(screen.getByText("正在处理")).toBeVisible();
    expect(screen.getByRole("link", { name: /返回项目/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}`,
    );
    expect(screen.getByRole("link", { name: /课堂 PPT/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons/${lessonId}/work/ppt`,
    );
  });
});
