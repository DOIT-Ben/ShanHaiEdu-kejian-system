import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation } from "react-router";
import { client, unwrap, qk, SESSION_EXPIRED_EVENT, AppError, type User } from "@/shared/api";
import { Spinner } from "@/shared/ui";

/** 会话（/auth/me）；401 时全局广播并回到登录页。 */
export function useSession() {
  return useQuery({
    queryKey: qk.session,
    queryFn: async () => {
      try {
        const result = unwrap(await client.GET("/auth/me"));
        return result.data.user;
      } catch (error) {
        if (error instanceof AppError && error.isSessionExpired) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

const SessionContext = createContext<User | null>(null);

export function useCurrentUser(): User {
  const user = useContext(SessionContext);
  if (!user) throw new Error("useCurrentUser 必须在已登录区域内使用");
  return user;
}

export function useIsAdmin(): boolean {
  const user = useContext(SessionContext);
  return Boolean(user?.roles.some((role) => role !== "teacher"));
}

/** 监听会话过期事件：清缓存，交由路由守卫跳转登录。 */
export function SessionExpiryListener() {
  const queryClient = useQueryClient();
  useEffect(() => {
    const handler = () => {
      queryClient.setQueryData(qk.session, null);
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  }, [queryClient]);
  return null;
}

function FullScreenLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <div className="flex flex-col items-center gap-3 text-ink-muted">
        <Spinner className="size-6" />
        <span className="text-sm">正在进入山海创作空间…</span>
      </div>
    </div>
  );
}

/** 登录守卫：未登录跳 /login 并记录回跳地址。 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useSession();
  const location = useLocation();
  if (isPending) return <FullScreenLoading />;
  if (!user) {
    const returnTo = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?return_to=${encodeURIComponent(returnTo)}`} replace />;
  }
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}

/** 管理端守卫：无管理角色显示 403（入口本身对教师隐藏）。 */
export function RequireAdmin({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useSession();
  const location = useLocation();
  if (isPending) return <FullScreenLoading />;
  if (!user) {
    const returnTo = `${location.pathname}${location.search}`;
    return <Navigate to={`/login?return_to=${encodeURIComponent(returnTo)}`} replace />;
  }
  if (!user.roles.some((role) => role !== "teacher")) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-canvas text-center">
        <h1 className="text-xl font-semibold text-ink-strong">没有管理权限</h1>
        <p className="text-sm text-ink-muted">当前账号无法访问管理端，如需权限请联系系统管理员。</p>
        <a href="/app" className="text-sm font-medium text-brand-600 hover:underline">
          返回教师端
        </a>
      </div>
    );
  }
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}
