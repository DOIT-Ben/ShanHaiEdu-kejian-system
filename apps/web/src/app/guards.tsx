import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { useSession, useSessionExpiryRedirect } from "@/features/session";
import { Spinner } from "@/shared/ui";
import type { UserRole } from "@/shared/api/types";

function FullscreenLoading({ label }: { label: string }) {
  return (
    <div className="flex h-screen items-center justify-center bg-page">
      <Spinner label={label} />
    </div>
  );
}

/** 登录守卫：会话恢复中显示加载；未登录跳转登录页并携带回跳地址。 */
export function RequireAuth({ children }: { children: ReactNode }) {
  useSessionExpiryRedirect();
  const session = useSession();
  const location = useLocation();

  if (session.isPending) {
    return <FullscreenLoading label="正在恢复登录状态…" />;
  }
  if (!session.data) {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`);
    return <Navigate to={`/login?redirect=${redirect}`} replace />;
  }
  return <>{children}</>;
}

const ADMIN_ROLES: UserRole[] = ["system_admin", "template_admin", "audit_admin"];

/** 管理后台守卫：非管理角色显示 403。 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const session = useSession();
  if (session.isPending) {
    return <FullscreenLoading label="正在校验权限…" />;
  }
  const role = session.data?.user.role;
  if (!role || !ADMIN_ROLES.includes(role)) {
    return <Navigate to="/403" replace />;
  }
  return <>{children}</>;
}

/** 已登录访问 /login 时跳回应用。 */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const session = useSession();
  if (session.isPending) {
    return <FullscreenLoading label="正在检查登录状态…" />;
  }
  if (session.data) {
    return <Navigate to="/app" replace />;
  }
  return <>{children}</>;
}
