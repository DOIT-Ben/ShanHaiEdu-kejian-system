import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectStepNavigation } from "@/features/workbench/components/ProjectStepNavigation";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

describe("ProjectStepNavigation active step visibility", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetMockRuntime();
  });

  it("切换步骤时只滚动流程栏，不带动整个页面", async () => {
    const base = `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work`;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
      this: HTMLElement,
    ) {
      if (this.hasAttribute("data-step-scroll-container")) {
        return DOMRect.fromRect({ height: 300, width: 240, x: 0, y: 0 });
      }
      if (this.textContent.includes("生成课堂导入视频")) {
        return DOMRect.fromRect({ height: 44, width: 220, x: 0, y: 316 });
      }
      return DOMRect.fromRect({ height: 44, width: 220, x: 0, y: 0 });
    });
    const windowScroll = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined);
    const elementScroll = vi.fn(function (this: HTMLElement, options?: ScrollToOptions | number) {
      if (typeof options === "object" && typeof options.top === "number") {
        this.scrollTop = options.top;
      }
    });
    Object.defineProperty(HTMLElement.prototype, "scrollTo", {
      configurable: true,
      value: elementScroll,
    });
    const { container } = render(
      <div data-step-scroll-container>
        <MemoryRouter initialEntries={[`${base}/lesson-plan`]}>
          <Routes>
            <Route
              element={<ProjectStepNavigation base={base} />}
              path="/app/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </div>,
    );

    const scrollContainer = container.querySelector<HTMLElement>("[data-step-scroll-container]");
    if (!scrollContainer) throw new Error("未找到流程滚动容器");
    scrollContainer.scrollTop = 20;
    elementScroll.mockClear();
    await userEvent.click(screen.getByRole("link", { name: /生成课堂导入视频/ }));
    await waitFor(() => expect(scrollContainer.scrollTop).toBe(208));
    expect(elementScroll).toHaveBeenCalledWith({ behavior: "smooth", top: 208 });
    expect(windowScroll).not.toHaveBeenCalled();
  });
});
