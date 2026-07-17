import { NavLink, Outlet, useNavigate } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, LogOut, Mountain, Search, Settings2 } from "lucide-react";
import { client, unwrapVoid } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/ui";
import { useCurrentUser, useIsAdmin } from "@/app/session";
import {
  useGlobalEventStream,
  useEventChannelStore,
  useActiveJobCount,
  CONNECTION_MODE_LABELS,
} from "@/features/generation-tasks";

/**
 * 全局框架（01 §2）：64px 顶部导航
 * 首页｜项目｜创作中心｜任务中心｜搜索｜通知｜头像。
 * 管理入口在头像菜单内，教师账号不显示。
 */

const NAV_ITEMS = [
  { to: "/app", label: "首页", end: true },
  { to: "/app/projects", label: "项目", end: false },
  { to: "/app/creation", label: "创作中心", end: false },
  { to: "/app/tasks", label: "任务中心", end: false },
];

function TopNavLink({ to, label, end, badge }: { to: string; label: string; end: boolean; badge?: number }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "relative flex h-16 items-center px-4 text-sm font-medium transition-colors duration-150",
          isActive ? "text-brand-600" : "text-ink hover:text-ink-strong",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span className="flex items-center gap-1.5">
            {label}
            {badge ? (
              <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-brand-500 px-1.5 text-xs font-semibold text-white">
                {badge}
              </span>
            ) : null}
          </span>
          {isActive ? (
            <span className="absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-brand-500" aria-hidden />
          ) : null}
        </>
      )}
    </NavLink>
  );
}

export function GlobalAppShell() {
  const user = useCurrentUser();
  const isAdmin = useIsAdmin();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  useGlobalEventStream(true);
  const activeJobs = useActiveJobCount();
  const channelMode = useEventChannelStore((s) => s.mode);
  const channelNotice = CONNECTION_MODE_LABELS[channelMode];

  const logout = useMutation({
    mutationFn: async () => {
      unwrapVoid(await client.POST("/auth/logout"));
    },
    onSettled: () => {
      queryClient.clear();
      void navigate("/login", { replace: true });
    },
  });

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 h-16 shrink-0 border-b border-line-subtle bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-full max-w-[var(--sh-content-max)] items-center gap-2 px-6">
          <NavLink to="/app" className="mr-4 flex items-center gap-2" aria-label="山海创作空间首页">
            <span className="flex size-8 items-center justify-center rounded-md bg-brand-500 text-white">
              <Mountain className="size-4.5" aria-hidden />
            </span>
            <span className="text-base font-semibold tracking-wide text-ink-strong">山海创作空间</span>
          </NavLink>
          <nav className="flex items-center" aria-label="主导航">
            {NAV_ITEMS.map((item) => (
              <TopNavLink
                key={item.to}
                {...item}
                badge={item.to === "/app/tasks" ? activeJobs : undefined}
              />
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              aria-label="搜索（即将上线）"
              title="搜索（即将上线）"
            >
              <Search className="size-4.5" aria-hidden />
            </Button>
            <Button variant="ghost" size="sm" aria-label="通知" onClick={() => void navigate("/app")}>
              <Bell className="size-4.5" aria-hidden />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="ml-1 flex size-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 outline-none transition-shadow focus-visible:shadow-focus"
                  aria-label={`账号菜单：${user.name}`}
                >
                  {user.name.slice(0, 1)}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel>
                  <div className="text-sm font-medium text-ink-strong">{user.name}</div>
                  <div className="text-xs font-normal text-ink-muted">{user.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {isAdmin ? (
                  <DropdownMenuItem onSelect={() => void navigate("/admin")}>
                    <Settings2 className="size-4" aria-hidden />
                    管理端
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuItem onSelect={() => logout.mutate()}>
                  <LogOut className="size-4" aria-hidden />
                  退出登录
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>
      {channelNotice ? (
        <div
          role="status"
          className="border-b border-warning-200 bg-warning-50 px-6 py-1.5 text-center text-xs text-warning-700"
        >
          {channelNotice}
        </div>
      ) : null}
      <main className="flex min-h-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}
