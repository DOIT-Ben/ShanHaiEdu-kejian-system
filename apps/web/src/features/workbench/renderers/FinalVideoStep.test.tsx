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

  it("连续点击生成只创建一个运行中的任务", () => {
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

    const button = screen.getByRole("button", { name: "开始生成视频" });
    fireEvent.click(button);
    fireEvent.click(button);

    const tasks = getMockRuntimeState().tasks.filter(
      (task) => task.node_run_id === finalVideoNodeId(),
    );
    expect(tasks).toHaveLength(1);
    expect(tasks[0]?.status).toBe("running");
    expect(screen.getByRole("button", { name: "视频生成中" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "正在生成" })).toBeDisabled();
  });

  it.each([
    { action: "重新生成视频", badge: "需要处理", status: "failed" },
    { action: "重新生成视频", badge: "已取消", status: "cancelled" },
    { action: "继续生成视频", badge: "已暂停", status: "paused" },
    { action: "重新生成视频", badge: "部分完成", status: "partially_completed" },
  ] as const)("任务为 $status 时禁止确认视频并提供恢复入口", async ({ action, badge, status }) => {
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

    fireEvent.click(screen.getByRole("button", { name: "开始生成视频" }));
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
    expect(screen.queryByRole("button", { name: "确认视频" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: action })).not.toHaveLength(0);
    expect(
      screen
        .getAllByRole("button", { name: action })
        .every((button) => !(button as HTMLButtonElement).disabled),
    ).toBe(true);
  });

  it("没有真实视频地址时只显示关键帧并禁止确认", () => {
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

    expect(screen.getByRole("button", { name: "视频尚未生成" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "确认视频" })).not.toBeInTheDocument();
    expect(screen.getAllByText(/关键帧示意/).length).toBeGreaterThan(0);
    expect(screen.queryByText("技术检查")).not.toBeInTheDocument();
    expect(screen.getByText("画面尚未检查")).toBeInTheDocument();
    expect(screen.getByText("声音尚未检查")).toBeInTheDocument();
    expect(screen.getByText("字幕尚未检查")).toBeInTheDocument();
  });

  it("只有明确的视频地址才开放播放与确认", () => {
    saveMockDraft(
      "project:project-a:lesson:lesson-a:final-video:media",
      { mimeType: "video/mp4", src: "https://cdn.example.com/final.mp4" },
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

    expect(screen.getByLabelText("果汁标签侦探课堂导入视频").tagName).toBe("VIDEO");
    expect(screen.getByRole("button", { name: "确认视频" })).toBeEnabled();
    expect(screen.getByText("画面正常")).toBeInTheDocument();
    expect(screen.getByText("声音清楚")).toBeInTheDocument();
    expect(screen.getByText("字幕易读")).toBeInTheDocument();
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
