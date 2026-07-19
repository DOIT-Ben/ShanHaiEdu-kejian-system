import * as Tooltip from "@radix-ui/react-tooltip";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ContextDrawer } from "@/features/workbench/components/ContextDrawer";
import { useWorkbenchUi } from "@/features/workbench/model/workbenchUi";
import {
  getMockDraft,
  getMockNodeState,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";

const projectId = "project-a";
const lessonId = "lesson-a";
const introDraftKey = `project:${projectId}:lesson:${lessonId}:intro-options`;

function renderDrawer() {
  render(
    <Tooltip.Provider>
      <MemoryRouter
        initialEntries={[`/app/projects/${projectId}/lessons/${lessonId}/work/intro-options`]}
      >
        <Routes>
          <Route
            element={
              <>
                <button
                  onClick={() => useWorkbenchUi.getState().openContextDrawer("prompt")}
                  type="button"
                >
                  编辑方案
                </button>
                <ContextDrawer />
              </>
            }
            path="/app/projects/:projectId/lessons/:lessonId/work/:stepKey"
          />
        </Routes>
      </MemoryRouter>
    </Tooltip.Provider>,
  );
}

describe("ContextDrawer regeneration lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    resetMockRuntime();
    useWorkbenchUi.setState({ contextDrawerOpen: false, contextTab: "references" });
  });

  afterEach(() => vi.useRealTimers());

  it("生成中保持面板打开，完成后关闭并把焦点还给触发按钮", async () => {
    const optionKey = "INTRO-APP-01";
    saveMockDraft(introDraftKey, {
      adoptedKey: optionKey,
      adoptedRevision: 0,
      previewKey: optionKey,
      previewRevision: 0,
      revisions: { [optionKey]: 0 },
    });
    updateMockNodeState(projectId, lessonId, "intro-options", {
      status: "approved",
      title: "选择课堂导入",
    });
    renderDrawer();
    const trigger = screen.getByRole("button", { name: "编辑方案" });
    trigger.focus();
    fireEvent.click(trigger);
    fireEvent.change(screen.getByRole("textbox", { name: "你希望怎样调整" }), {
      target: { value: "增加学生观察过程" },
    });
    fireEvent.click(screen.getByRole("button", { name: "按新要求重新生成" }));
    expect(screen.getByRole("status")).toHaveTextContent("正在按新要求准备方案");

    expect(screen.getByRole("button", { name: "生成完成后可关闭" })).toBeDisabled();
    await act(() => vi.advanceTimersByTimeAsync(700));

    expect(screen.getByRole("dialog", { name: "内容要求" })).toBeInTheDocument();
    expect(getMockDraft(introDraftKey)).toBeDefined();
    expect(getMockNodeState(projectId, lessonId, "intro-options")?.status).toBe("review_required");
    fireEvent.click(screen.getByRole("button", { name: "关闭面板" }));
    await act(() => vi.runOnlyPendingTimersAsync());
    expect(screen.queryByRole("dialog", { name: "内容要求" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
