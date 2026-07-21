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

  it("相邻步骤已经可见时只移动选中块，不滚动流程栏", async () => {
    const base = `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work`;
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (
      this: HTMLElement,
    ) {
      if (this.hasAttribute("data-step-scroll-container")) {
        return DOMRect.fromRect({ height: 300, width: 240, x: 0, y: 0 });
      }
      if (this.textContent.includes("选择课堂导入")) {
        return DOMRect.fromRect({ height: 44, width: 220, x: 0, y: 120 });
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
    const indicatorBefore = screen.getByTestId("project-step-active-indicator");
    const transformBefore = indicatorBefore.style.transform;
    await userEvent.click(screen.getByRole("link", { name: /选择课堂导入/ }));
    await waitFor(() => expect(indicatorBefore.style.transform).not.toBe(transformBefore));
    expect(elementScroll).not.toHaveBeenCalled();
    const indicatorAfter = screen.getByTestId("project-step-active-indicator");
    expect(indicatorAfter).toBe(indicatorBefore);
    expect(indicatorAfter.style.transform).not.toBe(transformBefore);
    expect(windowScroll).not.toHaveBeenCalled();
  });

  it("目标步骤超出可视区时只滚动到最近边界", async () => {
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
    await waitFor(() => expect(scrollContainer.scrollTop).toBe(128));
    expect(elementScroll).toHaveBeenCalledWith({ behavior: "smooth", top: 128 });
  });

  it("从项目创作台进入时仍高亮来源节点并使用项目上下文", () => {
    const base = `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work`;
    render(
      <MemoryRouter initialEntries={["/app/creation/images"]}>
        <ProjectStepNavigation
          activeStepKey="video-assets"
          base={base}
          lessonId={demoLessonId}
          projectId={demoProjectId}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("link", { name: /制作镜头图片 当前/ })).toHaveAttribute(
      "data-current",
      "true",
    );
  });
});
