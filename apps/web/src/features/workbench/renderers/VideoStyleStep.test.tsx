import { TooltipProvider } from "@radix-ui/react-tooltip";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { VideoStyleStep } from "@/features/workbench/renderers/VideoStyleStep";
import { resetMockRuntime, saveMockDraft, updateMockNodeState } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

function renderStep() {
  return render(
    <TooltipProvider>
      <MemoryRouter
        initialEntries={[`/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/video-style`]}
      >
        <Routes>
          <Route
            element={<VideoStyleStep />}
            path="/app/projects/:projectId/lessons/:lessonId/work/video-style"
          />
        </Routes>
      </MemoryRouter>
    </TooltipProvider>,
  );
}

describe("VideoStyleStep", () => {
  beforeEach(() => resetMockRuntime());

  it("选择候选后明确更新当前预览和无障碍反馈", () => {
    renderStep();

    const candidate = screen.getByRole("button", { name: "选择柔和黏土定格" });
    fireEvent.click(candidate);

    expect(candidate).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("点击候选查看大图 · 当前预览：柔和黏土定格")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("正在预览“柔和黏土定格”");
  });

  it("使用居中对话框重新设计画面", () => {
    renderStep();

    fireEvent.click(screen.getByRole("button", { name: "重新设计画面" }));

    expect(screen.getByRole("dialog", { name: "重新设计画面" })).toBeVisible();
    expect(screen.getByPlaceholderText(/保留暖色纸艺质感/)).toBeVisible();
  });

  it("确认风格后提供制作镜头图片的下一步", () => {
    const draftKey = `project:${demoProjectId}:lesson:${demoLessonId}:video-style`;
    saveMockDraft(
      `${draftKey}:approved`,
      { selectedId: "paper" },
      { lessonId: demoLessonId, nodeKey: "video-style", projectId: demoProjectId },
    );
    updateMockNodeState(demoProjectId, demoLessonId, "video-style", {
      status: "approved",
      title: "确定画面风格",
    });

    renderStep();

    expect(screen.getByRole("link", { name: "制作镜头图片" })).toHaveAttribute(
      "href",
      `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/video-assets`,
    );
  });
});
