import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TasksPage } from "@/pages/tasks/TasksPage";
import {
  readCreationQueue,
  saveCreationQueue,
} from "@/features/creation-studio/creationRuntimeAdapter";
import { getMockRuntimeState, resetMockRuntime } from "@/shared/api/mocks/runtime";

const creationQueueKey =
  "creation:image:project:project-a:lesson:lesson-a:package:video-assets:queue";

describe("TasksPage status feedback", () => {
  beforeEach(() => {
    resetMockRuntime();
    vi.useFakeTimers();
  });

  afterEach(() => vi.useRealTimers());

  it("重新连接经历 pending 后进入成功状态", async () => {
    render(
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "恢复更新" }));
    expect(screen.getByRole("button", { name: "正在恢复" })).toBeDisabled();

    await act(() => vi.advanceTimersByTimeAsync(450));

    expect(screen.getByText("进度实时更新中")).toBeInTheDocument();
  });

  it("连接失败后显示错误并允许重试", async () => {
    render(
      <MemoryRouter initialEntries={["/app/tasks?scenario=connection_error"]}>
        <TasksPage />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "恢复更新" }));
    await act(() => vi.advanceTimersByTimeAsync(450));

    expect(screen.getByRole("alert")).toHaveTextContent("进度仍未恢复");
    expect(screen.getByRole("button", { name: "重试" })).toBeEnabled();
  });

  it("向辅助技术公开任务进度", () => {
    render(
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>,
    );
    const progress = screen.getByRole("progressbar", { name: /课堂导入视频/ });
    expect(progress).toHaveAttribute("aria-valuemin", "0");
    expect(progress).toHaveAttribute("aria-valuemax", "100");
    expect(progress).toHaveAttribute("aria-valuenow", "68");
  });

  it("桌面任务使用紧凑列表密度", () => {
    render(
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>,
    );

    const rows = screen.getAllByRole("article");
    expect(rows.length).toBeGreaterThan(1);
    rows.forEach((row) => expect(row).toHaveAttribute("data-density", "compact"));
  });

  it("创作台任务在任务中心可见且暂停、取消、重试保持一致", () => {
    saveCreationQueue(
      creationQueueKey,
      { assetA: { attempts: 1, status: "running" } },
      { lessonId: "lesson-a", projectId: "project-a" },
    );
    render(
      <MemoryRouter>
        <TasksPage />
      </MemoryRouter>,
    );

    const taskRow = screen.getByRole("heading", { name: "生成课堂素材" }).closest("article");
    expect(taskRow).not.toBeNull();
    fireEvent.click(within(taskRow as HTMLElement).getByRole("button", { name: "暂停" }));
    expect(readCreationQueue(getMockRuntimeState(), creationQueueKey).assetA?.status).toBe(
      "paused",
    );

    fireEvent.click(within(taskRow as HTMLElement).getByRole("button", { name: "继续" }));
    expect(readCreationQueue(getMockRuntimeState(), creationQueueKey).assetA?.status).toBe(
      "running",
    );

    fireEvent.click(within(taskRow as HTMLElement).getByRole("button", { name: "取消" }));
    expect(readCreationQueue(getMockRuntimeState(), creationQueueKey).assetA?.status).toBe(
      "cancelled",
    );

    fireEvent.click(within(taskRow as HTMLElement).getByRole("button", { name: "重试" }));
    expect(readCreationQueue(getMockRuntimeState(), creationQueueKey).assetA?.status).toBe(
      "running",
    );
  });
});
