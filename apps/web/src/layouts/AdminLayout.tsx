import { NavLink, Outlet, Link } from "react-router";
import {
  ArrowLeft,
  ClipboardList,
  FileCog,
  Gauge,
  ShieldCheck,
  Users,
  Workflow,
} from "lucide-react";
import { cn } from "@/shared/lib/cn";

const NAV_ITEMS = [
  { to: "/admin/content", label: "内容中心", icon: FileCog },
  { to: "/admin/workflows", label: "工作流", icon: Workflow },
  { to: "/admin/models", label: "模型服务", icon: ShieldCheck },
  { to: "/admin/usage", label: "运行与费用", icon: Gauge },
  { to: "/admin/users", label: "用户权限", icon: Users },
  { to: "/admin/audit", label: "审计记录", icon: ClipboardList },
];

/** 管理端骨架（04 §2）：返回教师端｜六个板块。 */
export default function AdminLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="sticky top-0 z-40 border-b border-line-subtle bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[var(--sh-content-max)] items-center gap-4 px-6">
          <Link
            to="/app"
            className="flex items-center gap-1.5 text-sm font-medium text-ink-muted transition-colors duration-150 hover:text-ink-strong"
          >
            <ArrowLeft className="size-4" aria-hidden />
            返回教师端
          </Link>
          <span className="h-5 w-px bg-line" aria-hidden />
          <span className="text-base font-semibold text-ink-strong">管理端</span>
          <nav aria-label="管理端导航" className="ml-6 flex items-center gap-1 overflow-x-auto">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
                    isActive
                      ? "bg-brand-50 text-brand-600"
                      : "text-ink-muted hover:bg-surface-soft hover:text-ink-strong",
                  )
                }
              >
                <item.icon className="size-4" aria-hidden />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[var(--sh-content-max)] flex-1 px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
