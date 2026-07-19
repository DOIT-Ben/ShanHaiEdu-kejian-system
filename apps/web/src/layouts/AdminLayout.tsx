import { ArrowLeft, Boxes, FileClock, Gauge, KeyRound, Network, Users } from "lucide-react";
import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import brandMark from "@/assets/brand/brand-mark.svg";
import { cn } from "@/shared/lib/cn";
import { ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";

const adminNav = [
  { label: "内容中心", to: "/admin/content", icon: Boxes },
  { label: "工作流", to: "/admin/workflows", icon: Network },
  { label: "模型服务", to: "/admin/models", icon: KeyRound },
  { label: "运行与费用", to: "/admin/usage", icon: Gauge },
  { label: "用户权限", to: "/admin/users", icon: Users },
  { label: "审计记录", to: "/admin/audit", icon: FileClock },
];

export function AdminLayout() {
  const location = useLocation();
  const mobileNavRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mobileNavRef.current
      ?.querySelector<HTMLElement>('[aria-current="page"]')
      ?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-[var(--sh-surface-canvas)]">
      <header className="sticky top-0 z-30 flex h-[var(--sh-topbar-height)] items-center gap-3 border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]/92 px-4 backdrop-blur-[10px] md:px-6">
        <span className="grid size-9 place-items-center rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-1.5 shadow-[var(--sh-shadow-card)]">
          <img alt="" aria-hidden="true" className="size-full" src={brandMark} />
        </span>
        <div>
          <p className="text-xs text-[var(--sh-ink-muted)]">山海教育</p>
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">管理端</p>
        </div>
        <ThemeSwitcher className="ml-auto" showLabel />
        <NavLink
          aria-label="返回教师端"
          className="inline-flex min-h-10 items-center gap-2 rounded-[var(--sh-radius-sm)] px-2 text-sm font-semibold text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)] sm:px-3"
          to="/app"
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          <span className="hidden sm:inline">返回教师端</span>
        </NavLink>
      </header>
      <div className="mx-auto grid max-w-[1600px] md:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="hidden min-h-[calc(100vh-var(--sh-topbar-height))] border-r border-[var(--sh-line-default)] bg-[var(--sh-brand-50)] p-3 md:block">
          <nav aria-label="管理端导航" className="space-y-1">
            {adminNav.map(({ icon: Icon, label, to }) => (
              <NavLink
                className={({ isActive }) =>
                  cn(
                    "flex min-h-11 items-center gap-3 rounded-[var(--sh-radius-sm)] px-3 text-sm font-medium text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]",
                    isActive &&
                      "bg-[var(--sh-surface-soft)] font-semibold text-[var(--sh-brand-700)]",
                  )
                }
                key={to}
                to={to}
              >
                <Icon aria-hidden="true" className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="min-w-0">
          <div className="relative border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] md:hidden">
            <HorizontalScrollArea
              ariaLabel="管理端页面"
              hintTestId="admin-navigation-scroll-next"
              ref={mobileNavRef}
              viewportClassName="flex gap-1 px-3 pr-10 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {adminNav.map(({ label, to }) => (
                <NavLink
                  className={({ isActive }) =>
                    cn(
                      "shrink-0 border-b-2 border-transparent px-3 py-3 text-sm font-medium text-[var(--sh-ink-muted)]",
                      isActive &&
                        "border-[var(--sh-brand-500)] font-semibold text-[var(--sh-brand-700)]",
                    )
                  }
                  key={to}
                  to={to}
                >
                  {label}
                </NavLink>
              ))}
            </HorizontalScrollArea>
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
