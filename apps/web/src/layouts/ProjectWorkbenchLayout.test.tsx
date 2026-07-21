import { TooltipProvider } from "@radix-ui/react-tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes, useParams } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectWorkbenchLayout } from "@/layouts/ProjectWorkbenchLayout";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

function StepProbe() {
  const { stepKey = "" } = useParams();
  return (
    <div>
      <span>{stepKey}</span>
      <Link to={`../${stepKey === "lesson-plan" ? "intro-options" : "lesson-plan"}`}>切换节点</Link>
    </div>
  );
}

describe("ProjectWorkbenchLayout step navigation", () => {
  beforeEach(() => resetMockRuntime());

  it("切换节点时不强制滚动右侧内容区", async () => {
    const contentScroll = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: function (this: HTMLElement, options?: ScrollToOptions | number) {
        if (this.dataset.testid === "workbench-content") contentScroll(options);
      },
    });
    const base = `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work`;
    const queryClient = new QueryClient({
      defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[`${base}/lesson-plan`]}>
            <Routes>
              <Route
                element={<ProjectWorkbenchLayout />}
                path="/app/projects/:projectId/lessons/:lessonId/work"
              >
                <Route element={<StepProbe />} path=":stepKey" />
              </Route>
            </Routes>
          </MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    );

    contentScroll.mockClear();
    await userEvent.click(screen.getByRole("link", { name: "切换节点" }));
    expect(contentScroll).not.toHaveBeenCalled();
    expect(screen.getByText("intro-options")).toBeInTheDocument();
  });
});
