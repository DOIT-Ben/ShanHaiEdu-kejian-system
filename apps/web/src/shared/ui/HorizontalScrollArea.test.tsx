import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";

const observe = vi.fn();
const disconnect = vi.fn();

class ResizeObserverMock {
  disconnect = disconnect;
  observe = observe;
}

describe("HorizontalScrollArea", () => {
  beforeEach(() => {
    observe.mockClear();
    disconnect.mockClear();
    vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("同时观察视口与动态加入的直接内容", async () => {
    const { getByTestId, rerender } = render(
      <HorizontalScrollArea ariaLabel="测试横滑区">
        <div data-testid="first-item">第一项</div>
      </HorizontalScrollArea>,
    );

    await waitFor(() => expect(observe).toHaveBeenCalledWith(getByTestId("first-item")));

    rerender(
      <HorizontalScrollArea ariaLabel="测试横滑区">
        <div data-testid="first-item">第一项</div>
        <div data-testid="second-item">第二项</div>
      </HorizontalScrollArea>,
    );

    await waitFor(() => expect(observe).toHaveBeenCalledWith(getByTestId("second-item")));
  });
});
