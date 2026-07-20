import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { mockRuntime, resetMockRuntime, useMockRuntime } from "@/shared/api/mocks/runtime";

describe("useMockRuntime", () => {
  beforeEach(() => {
    localStorage.clear();
    resetMockRuntime();
  });

  it("does not rerender a selector consumer for an unrelated update", () => {
    let renderCount = 0;

    function ProjectCount() {
      renderCount += 1;
      const projectCount = useMockRuntime((state) => state.projects.length);
      return <output>{projectCount}</output>;
    }

    render(<ProjectCount />);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(renderCount).toBe(1);
    const task = mockRuntime.getState().tasks[0];
    expect(task).toBeDefined();
    if (!task) return;

    act(() => {
      mockRuntime.updateTask(task.id, { progress: 42 });
    });

    expect(renderCount).toBe(1);
  });
});
