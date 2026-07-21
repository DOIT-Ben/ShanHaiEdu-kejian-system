import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { RoughStoryboardStep } from "@/features/workbench/renderers/RoughStoryboardStep";
import { resetMockRuntime, saveMockDraft, updateMockNodeState } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

function renderStep() {
  return render(
    <MemoryRouter
      initialEntries={[
        `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/rough-storyboard`,
      ]}
    >
      <Routes>
        <Route
          element={<RoughStoryboardStep />}
          path="/app/projects/:projectId/lessons/:lessonId/work/rough-storyboard"
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RoughStoryboardStep accessibility", () => {
  beforeEach(() => resetMockRuntime());

  it("说明键盘排序方式并播报移动结果", () => {
    renderStep();

    const handle = screen.getByRole("button", {
      name: /拖动三瓶果汁进入画面；也可使用左右方向键移动/,
    });
    expect(handle).toHaveClass("text-[var(--sh-ink-muted)]");

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(screen.getByText("已将故事节拍移到第 2 位")).toHaveAttribute("aria-live", "polite");
  });

  it("确认后锁定镜头内容并提供画面风格下一步", () => {
    const draftKey = `project:${demoProjectId}:lesson:${demoLessonId}:rough-storyboard`;
    const items = [
      {
        assets: "三瓶果汁",
        event: "学生观察标签差异。",
        time: "0:00—0:18",
        title: "发现问题",
      },
    ];
    saveMockDraft(
      `${draftKey}:approved`,
      { approved: true, items },
      { lessonId: demoLessonId, nodeKey: "rough-storyboard", projectId: demoProjectId },
    );
    updateMockNodeState(demoProjectId, demoLessonId, "rough-storyboard", {
      status: "approved",
      title: "安排故事镜头",
    });

    renderStep();

    expect(screen.getByRole("link", { name: "确定画面风格" })).toHaveAttribute(
      "href",
      `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/video-style`,
    );
    expect(screen.getByRole("textbox", { name: "发现问题主要事件" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "增加故事节拍" })).not.toBeInTheDocument();
  });
});
