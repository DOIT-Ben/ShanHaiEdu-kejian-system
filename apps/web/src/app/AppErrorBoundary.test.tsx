import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppErrorBoundary } from "@/app/AppErrorBoundary";

function BrokenPage(): never {
  throw new Error("chunk failed");
}

describe("AppErrorBoundary", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  it("shows a user-facing route recovery screen when a page crashes", () => {
    render(
      <AppErrorBoundary>
        <BrokenPage />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: "页面暂时无法打开" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新加载" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回工作台首页" })).toHaveAttribute("href", "/app");
  });
});
