import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { PptCoverStep } from "@/features/workbench/renderers/PptCoverStep";
import {
  getMockRuntimeState,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";
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

  it("点击候选后立即勾选并更新无障碍反馈", () => {
    renderStep();

    const candidate = screen.getByRole("button", { name: "选择果汁标签" });
    fireEvent.click(candidate);

    expect(candidate).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("已选中：果汁标签")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("已选择“果汁标签”，继续后将作为 PPT 封面");
  });

  it("确认后仍可直接改选，不需要重新选择按钮", () => {
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

    expect(screen.getByRole("button", { name: "制作 PPT 正文" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "重新选择封面" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择百格光窗" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "选择果汁标签" }));
    expect(screen.getByRole("button", { name: "选择果汁标签" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(
      getMockRuntimeState().nodeStates[`${demoProjectId}:${demoLessonId}:ppt-cover`]?.status,
    ).toBe("review_required");
  });
});
