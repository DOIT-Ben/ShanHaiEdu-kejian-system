import { TooltipProvider } from "@radix-ui/react-tooltip";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RuntimeAppShell } from "@/layouts/RuntimeAppShell";

const sessionMocks = vi.hoisted(() => ({
  logout: vi.fn(),
  useSession: vi.fn(),
}));

vi.mock("@/features/session/SessionProvider", () => ({
  useSession: sessionMocks.useSession,
}));

describe("RuntimeAppShell production boundaries", () => {
  beforeEach(() => {
    sessionMocks.logout.mockReset();
    sessionMocks.useSession.mockReturnValue({
      login: vi.fn(),
      logout: sessionMocks.logout,
      refresh: vi.fn(),
      session: {
        csrf_token: "csrf-token",
        expires_at: "2026-07-24T00:00:00Z",
        principal: {
          display_name: "王老师",
          organization_id: "01960000-0000-7000-8000-000000000001",
          organization_name: "山海小学",
          organization_role: "member",
          principal_id: "01960000-0000-7000-8000-000000000002",
          user_id: "01960000-0000-7000-8000-000000000003",
        },
        session_id: "01960000-0000-7000-8000-000000000004",
      },
      status: "authenticated",
    });
  });

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

  it("从真实账户菜单撤销当前会话", async () => {
    const user = userEvent.setup();
    render(
      <TooltipProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route element={<RuntimeAppShell />} path="/">
              <Route element={<p>真实模式内容</p>} index />
            </Route>
            <Route element={<p>登录页</p>} path="/login" />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>,
    );

    await user.click(screen.getByRole("button", { name: "打开个人菜单" }));
    expect(screen.getByText("王老师 · 山海小学")).toBeVisible();
    await user.click(screen.getByRole("menuitem", { name: "退出登录" }));
    expect(sessionMocks.logout).toHaveBeenCalledOnce();
    expect(await screen.findByText("登录页")).toBeVisible();
  });
});
