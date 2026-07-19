import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RoughStoryboardStep } from "@/features/workbench/renderers/RoughStoryboardStep";

describe("RoughStoryboardStep accessibility", () => {
  it("说明键盘排序方式并播报移动结果", () => {
    render(<RoughStoryboardStep />);

    const handle = screen.getByRole("button", {
      name: /拖动三瓶果汁进入画面；也可使用左右方向键移动/,
    });
    expect(handle).toHaveClass("text-[var(--sh-ink-muted)]");

    fireEvent.keyDown(handle, { key: "ArrowRight" });
    expect(screen.getByText("已将故事节拍移到第 2 位")).toHaveAttribute("aria-live", "polite");
  });
});
