import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { FinalVideoStep } from "@/features/workbench/renderers/FinalVideoStep";
import {
  createMockTask,
  getMockRuntimeState,
  resetMockRuntime,
  saveMockDraft,
  updateMockNodeState,
  updateMockTask,
} from "@/shared/api/mocks/runtime";

describe("FinalVideoStep synthesis single flight", () => {
  beforeEach(() => resetMockRuntime());

  function finalVideoNodeId() {
    const nodeId = getMockRuntimeState().nodeStates["project-a:lesson-a:final-video"]?.id;
    if (!nodeId) throw new Error("缺少成片节点");
    return nodeId;
  }

  it("连续点击重新合成只创建一个运行中的任务", () => {
    render(
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/final-video"]}>
        <Routes>
          <Route
            element={<FinalVideoStep />}
            path="/projects/:projectId/lessons/:lessonId/work/final-video"
          />
        </Routes>
      </MemoryRouter>,
    );

    const button = screen.getByRole("button", { name: "重新合成" });
    fireEvent.click(button);
    fireEvent.click(button);

    const tasks = getMockRuntimeState().tasks.filter(
      (task) => task.node_run_id === finalVideoNodeId(),
    );
    expect(tasks).toHaveLength(1);
    expect(tasks[0]?.status).toBe("running");
    expect(screen.getByRole("button", { name: "成片合成中" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "正在合成" })).toBeDisabled();
  });

  it.each([
    { action: "重新合成", badge: "需要处理", status: "failed" },
    { action: "重新合成", badge: "已取消", status: "cancelled" },
    { action: "继续合成", badge: "已暂停", status: "paused" },
    { action: "重新合成", badge: "部分完成", status: "partially_completed" },
  ] as const)("任务为 $status 时禁止确认成片并提供恢复入口", async ({ action, badge, status }) => {
    render(
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/final-video"]}>
        <Routes>
          <Route
            element={<FinalVideoStep />}
            path="/projects/:projectId/lessons/:lessonId/work/final-video"
          />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "重新合成" }));
    const task = getMockRuntimeState().tasks.find(
      (item) => item.node_run_id === finalVideoNodeId(),
    );
    expect(task).toBeDefined();
    if (!task) return;
    updateMockTask(task.id, { progress: 100, status });

    await waitFor(() =>
      expect(getMockRuntimeState().nodeStates["project-a:lesson-a:final-video"]?.status).toBe(
        status,
      ),
    );
    expect(screen.getByText(badge)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "确认成片" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: action })).not.toHaveLength(0);
    expect(
      screen
        .getAllByRole("button", { name: action })
        .every((button) => !(button as HTMLButtonElement).disabled),
    ).toBe(true);
  });

  it("优先使用当前任务引用，不会被旧的同节点任务覆盖", async () => {
    updateMockNodeState("project-a", "lesson-a", "final-video", { status: "running" });
    const nodeRunId = finalVideoNodeId();
    const current = createMockTask({
      detail: "当前任务",
      node_run_id: nodeRunId,
      project_id: "project-a",
      stage: "合成中",
      status: "running",
      title: "当前合成",
    });
    createMockTask({
      detail: "旧任务",
      node_run_id: nodeRunId,
      project_id: "project-a",
      stage: "失败",
      status: "failed",
      title: "旧合成",
    });
    saveMockDraft(
      "project:project-a:lesson:lesson-a:final-video-task",
      { taskId: current.id },
      { lessonId: "lesson-a", nodeKey: "final-video", projectId: "project-a" },
    );
    render(
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/final-video"]}>
        <Routes>
          <Route
            element={<FinalVideoStep />}
            path="/projects/:projectId/lessons/:lessonId/work/final-video"
          />
        </Routes>
      </MemoryRouter>,
    );

    updateMockTask(current.id, { progress: 100, status: "approved" });
    await waitFor(() =>
      expect(getMockRuntimeState().nodeStates["project-a:lesson-a:final-video"]?.status).toBe(
        "review_required",
      ),
    );
  });

  it("任务引用丢失后仍按当前节点任务恢复完成状态", async () => {
    updateMockNodeState("project-a", "lesson-a", "final-video", { status: "running" });
    const current = createMockTask({
      detail: "当前任务",
      node_run_id: finalVideoNodeId(),
      project_id: "project-a",
      stage: "合成中",
      status: "running",
      title: "当前合成",
    });
    saveMockDraft(
      "project:project-a:lesson:lesson-a:final-video-task",
      { taskId: "missing-task" },
      { lessonId: "lesson-a", nodeKey: "final-video", projectId: "project-a" },
    );
    render(
      <MemoryRouter initialEntries={["/projects/project-a/lessons/lesson-a/work/final-video"]}>
        <Routes>
          <Route
            element={<FinalVideoStep />}
            path="/projects/:projectId/lessons/:lessonId/work/final-video"
          />
        </Routes>
      </MemoryRouter>,
    );

    updateMockTask(current.id, { progress: 100, status: "approved" });
    await waitFor(() =>
      expect(getMockRuntimeState().nodeStates["project-a:lesson-a:final-video"]?.status).toBe(
        "review_required",
      ),
    );
  });
});
