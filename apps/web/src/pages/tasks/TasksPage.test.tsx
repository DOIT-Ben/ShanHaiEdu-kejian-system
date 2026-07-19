import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TasksPage } from "@/pages/tasks/TasksPage";
import { resetMockRuntime } from "@/shared/api/mocks/runtime";

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
});
