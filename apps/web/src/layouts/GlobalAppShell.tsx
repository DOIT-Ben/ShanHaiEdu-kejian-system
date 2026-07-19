import { useNavigate } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";
import { signOut, useMockSession } from "@/shared/auth/mockAuth";

/**
 * Mock-only adapter. The visual shell itself is data-source agnostic; keeping
 * this session adapter at the development boundary prevents mock auth from
 * entering the real application bundle.
 */
export function GlobalAppShell() {
  const navigate = useNavigate();
  const session = useMockSession();
  const name = session?.user.name ?? "演示教师";
  return (
    <AppShell
      accountInitial={name.slice(0, 1)}
      accountLabel={`${name} · ${session?.user.role === "admin" ? "管理员" : "教师"}`}
      isAdmin={session?.user.role === "admin"}
      onSignOut={() => {
        signOut();
        void navigate("/login", { replace: true });
      }}
    />
  );
}
