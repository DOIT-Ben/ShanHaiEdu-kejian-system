import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSession } from "@/features/session/SessionProvider";
import { AppShell } from "@/layouts/AppShell";

function accountInitial(displayName: string) {
  return Array.from(displayName.trim())[0] ?? "用";
}

export function RuntimeAppShell() {
  const { logout, session, status } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [logoutError, setLogoutError] = useState("");

  if (status === "loading") {
    return (
      <div
        className="grid min-h-screen place-items-center bg-[var(--sh-surface-canvas)]"
        role="status"
      >
        <p className="text-sm text-[var(--sh-ink-muted)]">正在恢复会话</p>
      </div>
    );
  }
  if (status !== "authenticated" || session === null) {
    return (
      <Navigate replace state={{ from: `${location.pathname}${location.search}` }} to="/login" />
    );
  }

  const handleSignOut = async () => {
    setLogoutError("");
    try {
      await logout();
      await navigate("/login", { replace: true });
    } catch {
      setLogoutError("退出失败，请稍后再试");
    }
  };

  return (
    <>
      {logoutError ? (
        <div
          className="bg-[var(--sh-danger-soft)] px-4 py-2 text-center text-sm text-[var(--sh-danger-strong)]"
          role="alert"
        >
          {logoutError}
        </div>
      ) : null}
      <AppShell
        accountInitial={accountInitial(session.principal.display_name)}
        accountLabel={`${session.principal.display_name} · ${session.principal.organization_name}`}
        isAdmin={
          session.principal.organization_role === "owner" ||
          session.principal.organization_role === "admin"
        }
        notifications={[]}
        onSignOut={() => void handleSignOut()}
        searchEntries={[]}
      />
    </>
  );
}
