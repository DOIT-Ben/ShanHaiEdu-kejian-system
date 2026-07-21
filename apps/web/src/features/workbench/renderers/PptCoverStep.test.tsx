import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { PptCoverStep } from "@/features/workbench/renderers/PptCoverStep";
import { resetMockRuntime, saveMockDraft, updateMockNodeState } from "@/shared/api/mocks/runtime";
import { demoLessonId, demoProjectId } from "@/shared/data/mockData";

function renderStep() {
  return render(
    <MemoryRouter
      initialEntries={[`/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/ppt-cover`]}
    >
      <Routes>
        <Route
          element={<PptCoverStep />}
          path="/app/projects/:projectId/lessons/:lessonId/work/ppt-cover"
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PptCoverStep", () => {
  beforeEach(() => resetMockRuntime());

  it("切换候选时明确更新当前预览和无障碍反馈", () => {
    renderStep();

    const candidate = screen.getByRole("button", { name: "选择果汁标签" });
    fireEvent.click(candidate);

    expect(candidate).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("点击候选查看大图 · 当前预览：果汁标签")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "正在预览“果汁标签”，确认后将作为 PPT 封面",
    );
  });

  it("确认封面后保留下一步入口，并把候选作为缩略导航", () => {
    const draftKey = `project:${demoProjectId}:lesson:${demoLessonId}:ppt-cover`;
    saveMockDraft(
      draftKey,
      { selectedId: 1 },
      {
        lessonId: demoLessonId,
        nodeKey: "ppt-cover",
        projectId: demoProjectId,
      },
    );
    saveMockDraft(
      `${draftKey}:approved`,
      { selectedId: 1 },
      {
        lessonId: demoLessonId,
        nodeKey: "ppt-cover",
        projectId: demoProjectId,
      },
    );
    updateMockNodeState(demoProjectId, demoLessonId, "ppt-cover", {
      status: "approved",
      title: "设计封面",
    });

    renderStep();

    expect(screen.getByRole("link", { name: "制作 PPT 正文" })).toHaveAttribute(
      "href",
      `/app/projects/${demoProjectId}/lessons/${demoLessonId}/work/ppt-pages`,
    );
    expect(screen.getByRole("button", { name: "选择百格光窗" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择果汁标签" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择课堂发现" })).toBeInTheDocument();
  });
});
