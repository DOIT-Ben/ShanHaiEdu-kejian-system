import { TooltipProvider } from "@radix-ui/react-tooltip";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RuntimeAppShell } from "@/layouts/RuntimeAppShell";

describe("RuntimeAppShell production boundaries", () => {
  it("真实模式的搜索和通知不会展示演示项目记录", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route element={<RuntimeAppShell />} path="/">
              <Route element={<p>真实模式内容</p>} index />
            </Route>
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    await user.click(screen.getByRole("button", { name: "搜索" }));
    expect(screen.getByText("当前没有可搜索的项目或功能。")).toBeVisible();
    expect(screen.queryByText("第 1 课时 · 百分数的意义")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "关闭搜索" }));

    await user.click(screen.getByRole("button", { name: /^通知$/ }));
    expect(await screen.findByText("暂无新通知")).toBeVisible();
    expect(screen.queryByText("教案已完成检查")).not.toBeInTheDocument();
  });
});
