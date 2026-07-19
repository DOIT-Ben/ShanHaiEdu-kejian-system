import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectStepNavigation } from "@/features/workbench/components/ProjectStepNavigation";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

const scrollIntoView = vi.fn();
const originalScrollIntoView = Object.getOwnPropertyDescriptor(
  HTMLElement.prototype,
  "scrollIntoView",
);

describe("ProjectStepNavigation active step visibility", () => {
  beforeAll(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });
  });

  beforeEach(() => {
    resetMockRuntime();
    scrollIntoView.mockClear();
  });

  afterAll(() => {
    if (originalScrollIntoView) {
      Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScrollIntoView);
    } else {
      Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
    }
  });

  it("打开后把当前制作步骤滚入流程视口", async () => {
    const base = `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work`;
    render(
      <MemoryRouter initialEntries={[`${base}/final-video`]}>
        <Routes>
          <Route
            element={<ProjectStepNavigation base={base} />}
            path="/app/projects/:projectId/lessons/:lessonId/work/:stepKey"
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /生成课堂导入视频.*当前/ })).toBeInTheDocument();
    await waitFor(() =>
      expect(scrollIntoView).toHaveBeenCalledWith({ block: "nearest", inline: "nearest" }),
    );
  });
});
