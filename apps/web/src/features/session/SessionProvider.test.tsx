import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, useSession } from "@/features/session/SessionProvider";
import { ApiError, isCsrfTokenAvailable } from "@/shared/api/client";

const apiMocks = vi.hoisted(() => ({
  createTeacherSession: vi.fn(),
  deleteCurrentSession: vi.fn(),
  getCurrentSession: vi.fn(),
}));

vi.mock("@/features/session/api/sessionApi", () => apiMocks);

const currentSession = {
  csrf_token: "placeholder-csrf-token-from-server",
  expires_at: "2026-07-24T00:00:00Z",
  principal: {
    display_name: "王老师",
    organization_id: "01960000-0000-7000-8000-000000000001",
    organization_name: "山海小学",
    organization_role: "member" as const,
    principal_id: "01960000-0000-7000-8000-000000000002",
    user_id: "01960000-0000-7000-8000-000000000003",
  },
  session_id: "01960000-0000-7000-8000-000000000004",
};

function SessionProbe() {
  const { login, logout, session, status } = useSession();
  return (
    <div>
      <span>{status}</span>
      <span>{session?.principal.display_name}</span>
      <button onClick={() => void login("controlled-access-code")} type="button">
        login
      </button>
      <button onClick={() => void logout()} type="button">
        logout
      </button>
    </div>
  );
}

describe("SessionProvider", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("从真实 API 恢复会话、提供 CSRF，并在登出后清空", async () => {
    apiMocks.getCurrentSession.mockResolvedValue(currentSession);
    apiMocks.deleteCurrentSession.mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(
      <SessionProvider>
        <SessionProbe />
      </SessionProvider>,
    );

    expect(await screen.findByText("authenticated")).toBeVisible();
    expect(screen.getByText("王老师")).toBeVisible();
    expect(isCsrfTokenAvailable()).toBe(true);

    await user.click(screen.getByRole("button", { name: "logout" }));
    await waitFor(() => expect(screen.getByText("anonymous")).toBeVisible());
    expect(apiMocks.deleteCurrentSession).toHaveBeenCalledWith(
      "placeholder-csrf-token-from-server",
    );
    expect(isCsrfTokenAvailable()).toBe(false);
  });

  it("忽略早于成功登录发起的迟到刷新 401", async () => {
    let rejectRefresh: (reason: unknown) => void = () => undefined;
    apiMocks.getCurrentSession.mockReturnValue(
      new Promise((_, reject) => {
        rejectRefresh = reject;
      }),
    );
    apiMocks.createTeacherSession.mockResolvedValue(currentSession);
    const user = userEvent.setup();

    render(
      <SessionProvider>
        <SessionProbe />
      </SessionProvider>,
    );

    await waitFor(() => expect(apiMocks.getCurrentSession).toHaveBeenCalledOnce());
    await user.click(screen.getByRole("button", { name: "login" }));
    expect(await screen.findByText("authenticated")).toBeVisible();

    rejectRefresh(
      new ApiError({
        error: {
          code: "AUTHENTICATION_REQUIRED",
          message: "Authentication is required.",
          retryable: false,
        },
        request_id: "req-stale-refresh",
      }),
    );

    await waitFor(() => expect(screen.getByText("authenticated")).toBeVisible());
    expect(screen.getByText("王老师")).toBeVisible();
  });
});
