import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RuntimeLoginPage } from "@/pages/runtime/RuntimeLoginPage";

const sessionMocks = vi.hoisted(() => ({
  login: vi.fn(),
  refresh: vi.fn(),
  useSession: vi.fn(),
}));

vi.mock("@/features/session/SessionProvider", () => ({
  useSession: sessionMocks.useSession,
}));

describe("RuntimeLoginPage", () => {
  beforeEach(() => {
    sessionMocks.login.mockReset();
    sessionMocks.refresh.mockReset();
    sessionMocks.useSession.mockReturnValue({
      login: sessionMocks.login,
      logout: vi.fn(),
      refresh: sessionMocks.refresh,
      session: null,
      status: "anonymous",
    });
  });

  it("只提交受控访问码，不呈现静态账号或密码身份", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RuntimeLoginPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "进入山海教育" })).toBeInTheDocument();
    expect(screen.queryByLabelText("账号")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("密码")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("学校访问码"), "controlled-access-code");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect(sessionMocks.login).toHaveBeenCalledWith("controlled-access-code");
  });
});
