import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { WorkStepPage } from "@/pages/projects/WorkStepPage";
import { introOptions } from "@/features/intro-options/data";
import {
  getMockRuntimeState,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
} from "@/shared/api/mocks/runtime";

describe("WorkStepPage route isolation", () => {
  beforeEach(() => {
    resetMockRuntime();
    for (const [projectId, lessonId] of [
      ["project-a", "lesson-a"],
      ["project-b", "lesson-b"],
    ] as const) {
      saveMockDraft(
        `project:${projectId}:lessons-approved`,
        [{ id: lessonId, title: `${lessonId} · 测试课时` }],
        { projectId, nodeKey: "lesson-division" },
      );
      updateMockNodeState(projectId, null, "lesson-division", {
        status: "approved",
        title: "安排课时",
      });
    }
  });

  it("切换课时后重新挂载步骤，避免沿用上一课时的未保存状态", () => {
    updateMockNodeState("project-a", null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });
    updateMockNodeState("project-b", null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/lesson-plan"]}>
          <Link to="/projects/project-b/lessons/lesson-b/work/lesson-plan">切换到课时 B</Link>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    fireEvent.change(screen.getByRole("textbox", { name: "教案正文" }), {
      target: { value: "课时 A 的未保存内容" },
    });
    fireEvent.click(screen.getByRole("link", { name: "切换到课时 B" }));

    expect(screen.queryByRole("textbox", { name: "教案正文" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    expect(screen.getByRole("textbox", { name: "教案正文" })).not.toHaveValue(
      "课时 A 的未保存内容",
    );
    expect(screen.getByTestId("work-step-transition")).toHaveAttribute(
      "data-step-key",
      "lesson-plan",
    );
  });

  it("前置步骤未确认时只显示解锁入口", () => {
    updateMockNodeState("project-a", "lesson-a", "lesson-plan", {
      status: "review_required",
      title: "编写并确认教案",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/ppt-outline"]}>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("heading", { name: "先确认教案" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去确认教案" })).toHaveAttribute(
      "href",
      "/app/projects/project-a/lessons/lesson-a/work/lesson-plan",
    );
    expect(screen.queryByRole("button", { name: "确认页面安排" })).not.toBeInTheDocument();
  });

  it("批准后的教案默认只读，重新编辑后才开放", () => {
    updateMockNodeState("project-a", null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });
    updateMockNodeState("project-a", "lesson-a", "lesson-plan", {
      status: "approved",
      title: "生成教案",
    });
    updateMockNodeState("project-a", "lesson-a", "ppt-pages", {
      status: "approved",
      title: "制作 PPT 正文",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/lesson-plan"]}>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("button", { name: "重新编辑教案" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "编辑" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重新编辑教案" }));
    expect(screen.getByRole("button", { name: "编辑" })).not.toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    fireEvent.change(screen.getByRole("textbox", { name: "教案正文" }), {
      target: { value: "新的教案内容" },
    });
    fireEvent.click(screen.getByRole("button", { name: "确认新教案" }));
    expect(getMockRuntimeState().nodeStates["project-a:lesson-a:ppt-pages"]?.status).toBe("stale");
  });

  it("批准后的母版剧本直接暴露预览和编辑，修改后回到待确认", () => {
    const option = introOptions[0];
    expect(option).toBeDefined();
    if (!option) return;
    saveMockDraft(
      "project:project-a:lesson:lesson-a:intro-options",
      {
        adoptedKey: option.key,
        adoptedRevision: 0,
        previewKey: option.key,
        previewRevision: 0,
        revisions: { [option.key]: 0 },
      },
      { lessonId: "lesson-a", nodeKey: "intro-options", projectId: "project-a" },
    );
    updateMockNodeState("project-a", "lesson-a", "intro-options", {
      status: "approved",
      title: "选择课堂导入",
    });
    updateMockNodeState("project-a", "lesson-a", "master-script", {
      status: "approved",
      title: "编写母版剧本",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/master-script"]}>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.queryByRole("button", { name: "重新编辑剧本" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "预览" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    fireEvent.change(screen.getByRole("textbox", { name: "母版剧本正文" }), {
      target: { value: "# 修改后的完整故事" },
    });
    expect(getMockRuntimeState().nodeStates["project-a:lesson-a:master-script"]?.status).toBe(
      "review_required",
    );
  });

  it("批准后的 PPT 页面安排锁定，重新编辑后才允许调整", () => {
    updateMockNodeState("project-a", null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });
    updateMockNodeState("project-a", "lesson-a", "lesson-plan", {
      status: "approved",
      title: "生成教案",
    });
    updateMockNodeState("project-a", "lesson-a", "ppt-outline", {
      status: "approved",
      title: "安排 PPT 页面",
    });
    updateMockNodeState("project-a", "lesson-a", "ppt-pages", {
      status: "approved",
      title: "制作 PPT 正文",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/ppt-outline"]}>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("button", { name: "重新编辑页面安排" })).toBeInTheDocument();
    expect(screen.getAllByRole("textbox").every((input) => input.hasAttribute("disabled"))).toBe(
      true,
    );
    fireEvent.click(screen.getByRole("button", { name: "重新编辑页面安排" }));
    expect(screen.getAllByRole("textbox")[0]).not.toBeDisabled();
    expect(getMockRuntimeState().nodeStates["project-a:lesson-a:ppt-pages"]?.status).toBe(
      "approved",
    );
    const firstTextbox = screen.getAllByRole("textbox")[0];
    if (!firstTextbox) throw new Error("缺少 PPT 页面输入框");
    fireEvent.change(firstTextbox, { target: { value: "改过的页面" } });
    fireEvent.click(screen.getByRole("button", { name: "确认新页面安排" }));
    expect(getMockRuntimeState().nodeStates["project-a:lesson-a:ppt-pages"]?.status).toBe("stale");
  });

  it("不存在的课时直达地址不会创建伪造教案", () => {
    updateMockNodeState("project-a", null, "lesson-division", {
      status: "approved",
      title: "安排课时",
    });

    render(
      <TooltipProvider>
        <MemoryRouter
          initialEntries={["/projects/project-a/lessons/not-a-real-lesson/work/lesson-plan"]}
        >
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByRole("heading", { name: "找不到这个课时" })).toBeInTheDocument();
  });

  it("课堂导入生成新预览后，在采用前保持待确认", () => {
    const first = introOptions[0];
    const second = introOptions[1];
    expect(first).toBeDefined();
    expect(second).toBeDefined();
    if (!first || !second) return;
    saveMockDraft(
      "project:project-a:lesson:lesson-a:intro-options",
      {
        adoptedKey: first.key,
        adoptedRevision: 0,
        previewKey: first.key,
        previewRevision: 0,
        revisions: { [first.key]: 0 },
      },
      { lessonId: "lesson-a", nodeKey: "intro-options", projectId: "project-a" },
    );
    updateMockNodeState("project-a", "lesson-a", "intro-options", {
      status: "approved",
      title: "选择课堂导入",
    });

    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/intro-options"]}>
          <Routes>
            <Route
              element={<WorkStepPage />}
              path="/projects/:projectId/lessons/:lessonId/work/:stepKey"
            />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    expect(screen.getByText("已完成")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: new RegExp(second.title) }));
    expect(getMockRuntimeState().nodeStates["project-a:lesson-a:intro-options"]?.status).toBe(
      "review_required",
    );
    expect(screen.getByText("等待你确认")).toBeInTheDocument();
  });
});
