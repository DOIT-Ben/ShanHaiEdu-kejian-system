import { act, fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PptPagesStep } from "@/features/workbench/renderers/PptPagesStep";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import {
  getMockDraft,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";

type PptPagesDraft = {
  content?: Record<string, string>;
  pageRevisions?: Record<string, number>;
  regeneratedPages?: number[];
};
const draftKey = "project:project-a:lesson:lesson-a:ppt-pages";

function renderStep() {
  return render(
    <TooltipProvider>
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/ppt-pages"]}>
        <Routes>
          <Route
            element={<PptPagesStep />}
            path="/projects/:projectId/lessons/:lessonId/work/ppt-pages"
          />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  );
}

describe("PptPagesStep delayed regeneration", () => {
  beforeEach(() => {
    resetMockRuntime();
    useWorkbenchUi.setState({ contextDrawerOpen: false, contextTab: "references" });
    vi.useFakeTimers();
  });

  afterEach(() => vi.useRealTimers());

  it("连续重做不同页面时合并每个 timeout 的结果", async () => {
    renderStep();
    fireEvent.click(screen.getByRole("button", { name: "重新生成本页" }));
    fireEvent.click(screen.getByRole("button", { name: /4\. 百分数表示什么/ }));
    fireEvent.click(screen.getByRole("button", { name: "重新生成本页" }));

    await act(() => vi.advanceTimersByTimeAsync(500));

    expect(getMockDraft<PptPagesDraft>(draftKey)?.value.regeneratedPages).toEqual([2, 3]);
  });

  it("重新生成后画布内容真实变化", async () => {
    const { container } = renderStep();
    const previewImage = container.querySelector('[role="img"] img');
    expect(previewImage).toHaveAttribute("src", "/assets/creation/slide-percent-grid.svg");
    expect(screen.queryByTestId("ppt-regenerated-note")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重新生成本页" }));
    await act(() => vi.advanceTimersByTimeAsync(500));

    expect(previewImage).toHaveAttribute("src", "/assets/creation/slide-percent-grid.svg");
    expect(screen.getByTestId("ppt-regenerated-note")).toHaveTextContent(
      "先观察：涂色部分占整体多少？",
    );
    expect(getMockDraft<PptPagesDraft>(draftKey)?.value.pageRevisions).toMatchObject({ "2": 1 });
  });

  it("工具名称与打开的内容面板一致", () => {
    renderStep();

    fireEvent.click(screen.getByRole("button", { name: "查看检查结果" }));
    expect(useWorkbenchUi.getState()).toMatchObject({
      contextDrawerOpen: true,
      contextTab: "checks",
    });
    fireEvent.click(screen.getByRole("button", { name: "查看参考内容" }));
    expect(useWorkbenchUi.getState().contextTab).toBe("references");
    fireEvent.click(screen.getByRole("button", { name: "编辑内容要求" }));
    expect(useWorkbenchUi.getState().contextTab).toBe("prompt");
  });

  it("卸载时取消尚未执行的重做任务", async () => {
    const { unmount } = renderStep();
    fireEvent.click(screen.getByRole("button", { name: "重新生成本页" }));
    unmount();

    await act(() => vi.advanceTimersByTimeAsync(500));

    expect(getMockDraft<PptPagesDraft>(draftKey)).toBeUndefined();
  });

  it("重新生成时通过状态区域播报进度和完成结果", async () => {
    renderStep();
    fireEvent.click(screen.getByRole("button", { name: "重新生成本页" }));
    expect(screen.getByRole("status")).toHaveTextContent("正在重新生成");

    await act(() => vi.advanceTimersByTimeAsync(500));

    expect(screen.getByRole("status")).toHaveTextContent("已重新生成并保存");
  });

  it("确认后的 PPT 默认锁定，明确重新编辑后才开放内容", () => {
    saveMockDraft(
      draftKey,
      { approved: true, content: {}, page: 0, pageRevisions: {}, regeneratedPages: [] },
      { lessonId: "lesson-a", nodeKey: "ppt-pages", projectId: "project-a" },
    );
    updateMockNodeState("project-a", "lesson-a", "ppt-pages", {
      status: "approved",
      title: "制作 PPT 正文",
    });

    const { container } = renderStep();

    expect(container.querySelector('[contenteditable="true"]')).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "重新编辑 PPT" }));
    expect(container.querySelector('[contenteditable="true"]')).not.toBeNull();
  });

  it("上游更新后以 node stale 为准并解释复核原因", () => {
    saveMockDraft(
      draftKey,
      { approved: true, content: {}, page: 0, pageRevisions: {}, regeneratedPages: [] },
      { lessonId: "lesson-a", nodeKey: "ppt-pages", projectId: "project-a" },
    );
    updateMockNodeState("project-a", "lesson-a", "ppt-pages", {
      stale_reason: { summary: "教案已批准新版本，请更新相关课件内容" },
      status: "stale",
      title: "制作 PPT 正文",
    });

    const { container } = renderStep();

    expect(screen.getByText("内容已变化，建议更新")).toBeInTheDocument();
    expect(screen.getByText("教案已批准新版本，请更新相关课件内容")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "检查并导出" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认整套 PPT" })).toBeEnabled();
    expect(container.querySelector('[contenteditable="true"]')).not.toBeNull();
  });
});
