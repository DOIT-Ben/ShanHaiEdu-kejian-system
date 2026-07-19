import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Menu, Plus, Search, Waves } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { GlobalSearchDialog } from "@/features/navigation/GlobalSearchDialog";
import { NotificationMenu } from "@/features/navigation/NotificationMenu";
import { signOut, useMockSession } from "@/shared/auth/mockAuth";
import { cn } from "@/shared/lib/cn";
import { ThemeMenuItems, ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import { IconButton } from "@/shared/ui/IconButton";

const navigation = [
  { label: "首页", to: "/app" },
  { label: "项目", to: "/app/projects" },
  { label: "创作中心", to: "/app/creation" },
  { label: "任务中心", to: "/app/tasks" },
];

export function GlobalAppShell() {
  const navigate = useNavigate();
  const session = useMockSession();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [accountNotice, setAccountNotice] = useState("");

  return (
    <div className="min-h-screen bg-[var(--sh-surface-canvas)]">
      <a
        className="sr-only z-50 rounded-md bg-[var(--sh-surface-elevated)] px-3 py-2 text-sm font-semibold text-[var(--sh-brand-700)] focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
        href="#main-content"
      >
        跳到主要内容
      </a>
      <header className="sticky top-0 z-40 h-[var(--sh-topbar-height)] border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/92 shadow-[var(--sh-shadow-card)] backdrop-blur-[10px]">
        <div className="mx-auto flex h-full max-w-[1600px] items-center gap-3 px-4 md:px-6">
          <NavLink
            aria-label="山海教育课件系统首页"
            className="flex shrink-0 items-center gap-2"
            to="/app"
          >
            <span className="grid size-9 place-items-center rounded-[var(--sh-radius-md)] bg-[image:var(--sh-action-gradient)] text-white shadow-[var(--sh-shadow-card)]">
              <Waves aria-hidden="true" className="size-5" />
            </span>
            <span className="hidden font-bold text-[var(--sh-ink-strong)] sm:inline">山海教育</span>
          </NavLink>

          <nav aria-label="全局导航" className="ml-4 hidden h-full items-center gap-1 lg:flex">
            {navigation.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  cn(
                    "relative flex h-full items-center px-4 text-sm font-medium text-[var(--sh-ink-muted)] transition-colors duration-[var(--sh-duration-fast)] hover:text-[var(--sh-brand-700)]",
                    isActive &&
                      "font-semibold text-[var(--sh-brand-700)] after:absolute after:inset-x-4 after:bottom-0 after:h-[3px] after:rounded-t-full after:bg-[var(--sh-brand-500)]",
                  )
                }
                end={item.to === "/app"}
                key={item.to}
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-1">
            <IconButton label="搜索" onClick={() => setSearchOpen(true)}>
              <Search aria-hidden="true" />
            </IconButton>
            <NotificationMenu />
            <ThemeSwitcher />
            <NavLink
              aria-label="新建课件"
              className="hidden min-h-10 items-center gap-1.5 rounded-[var(--sh-radius-md)] bg-[image:var(--sh-action-gradient)] px-3.5 text-sm font-semibold text-white shadow-[var(--sh-shadow-card)] transition-[box-shadow,transform] duration-[var(--sh-duration-fast)] hover:-translate-y-0.5 hover:bg-[image:var(--sh-action-gradient-hover)] hover:shadow-[var(--sh-shadow-hover)] sm:inline-flex"
              to="/app/projects/new"
            >
              <Plus aria-hidden="true" className="size-4" />
              新建课件
            </NavLink>
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <button
                  aria-label="打开个人菜单"
                  className="ml-1 flex min-h-10 items-center gap-2 rounded-[var(--sh-radius-sm)] px-2 hover:bg-[var(--sh-surface-soft)]"
                  type="button"
                >
                  <span className="grid size-8 place-items-center rounded-full bg-[var(--sh-warning-soft)] text-sm font-semibold text-[var(--sh-warning)]">
                    {session?.user.name.slice(0, 1) ?? "用"}
                  </span>
                  <ChevronDown aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
                </button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content
                  align="end"
                  className="z-50 min-w-48 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-1.5 shadow-[var(--sh-shadow-floating)]"
                  sideOffset={8}
                >
                  <DropdownMenu.Label className="px-3 py-2 text-xs text-[var(--sh-ink-muted)]">
                    {session?.user.name ?? "当前用户"} ·{" "}
                    {session?.user.role === "admin" ? "管理员" : "教师"}
                  </DropdownMenu.Label>
                  <DropdownMenu.Separator className="my-1 h-px bg-[var(--sh-line-subtle)]" />
                  {session?.user.role === "admin" ? (
                    <DropdownMenu.Item asChild>
                      <NavLink
                        className="block rounded-md px-3 py-2 text-sm outline-none hover:bg-[var(--sh-surface-soft)]"
                        to="/admin/content"
                      >
                        进入管理端
                      </NavLink>
                    </DropdownMenu.Item>
                  ) : null}
                  <ThemeMenuItems />
                  <DropdownMenu.Item
                    className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none hover:bg-[var(--sh-surface-soft)]"
                    onSelect={() => setAccountNotice("账号资料由学校管理员统一维护。")}
                  >
                    账号设置
                  </DropdownMenu.Item>
                  <DropdownMenu.Item
                    className="cursor-pointer rounded-md px-3 py-2 text-sm outline-none hover:bg-[var(--sh-surface-soft)]"
                    onSelect={() => {
                      signOut();
                      void navigate("/login", { replace: true });
                    }}
                  >
                    退出登录
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            <IconButton
              aria-controls="mobile-navigation"
              aria-expanded={mobileOpen}
              className="lg:hidden"
              label={mobileOpen ? "关闭导航" : "打开导航"}
              onClick={() => setMobileOpen((value) => !value)}
            >
              <Menu aria-hidden="true" />
            </IconButton>
          </div>
        </div>
        {mobileOpen ? (
          <nav
            aria-label="移动端导航"
            className="border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-4 py-3 shadow-[var(--sh-shadow-card)] lg:hidden"
            id="mobile-navigation"
          >
            {navigation.map((item) => (
              <NavLink
                className={({ isActive }) =>
                  cn(
                    "block rounded-md px-3 py-2 text-sm font-medium hover:bg-[var(--sh-surface-soft)]",
                    isActive && "bg-[var(--sh-brand-50)] font-semibold text-[var(--sh-brand-700)]",
                  )
                }
                key={item.to}
                onClick={() => setMobileOpen(false)}
                to={item.to}
              >
                {item.label}
              </NavLink>
            ))}
            <button
              className="mt-1 flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm font-medium hover:bg-[var(--sh-surface-soft)]"
              onClick={() => {
                setMobileOpen(false);
                setSearchOpen(true);
              }}
              type="button"
            >
              <Search aria-hidden="true" className="size-4" />
              搜索项目和功能
            </button>
          </nav>
        ) : null}
      </header>
      {accountNotice ? (
        <div
          className="border-b border-[var(--sh-line-subtle)] bg-[var(--sh-brand-50)] px-5 py-2 text-center text-sm text-[var(--sh-brand-700)]"
          role="status"
        >
          {accountNotice}
        </div>
      ) : null}
      <main id="main-content">
        <Outlet />
      </main>
      <GlobalSearchDialog onOpenChange={setSearchOpen} open={searchOpen} />
    </div>
  );
}
