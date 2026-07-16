import { NavLink, Outlet } from "react-router";
import {
  Activity,
  FileCode2,
  Gauge,
  Network,
  ScrollText,
  Users,
  Workflow,
} from "lucide-react";
import { useSession } from "@/features/session";
import { cn } from "@/shared/lib/cn";
import type { UserRole } from "@/shared/api/types";

interface AdminNavItem {
  to: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  roles: UserRole[];
  end?: boolean;
}

const ADMIN_NAV: AdminNavItem[] = [
  { to: "/admin", label: "仪表盘", icon: Gauge, roles: ["system_admin", "template_admin", "audit_admin"], end: true },
  { to: "/admin/templates", label: "Prompt模板", icon: FileCode2, roles: ["system_admin", "template_admin"] },
  { to: "/admin/model-gateway", label: "模型网关", icon: Network, roles: ["system_admin", "audit_admin"] },
  { to: "/admin/workflows", label: "工作流模板", icon: Workflow, roles: ["system_admin", "template_admin"] },
  { to: "/admin/users", label: "用户与权限", icon: Users, roles: ["system_admin"] },
  { to: "/admin/audit", label: "审计记录", icon: ScrollText, roles: ["system_admin", "audit_admin"] },
];

/** 管理后台布局：左侧功能导航，按角色过滤可见项。 */
export function AdminLayout() {
  const session = useSession();
  const role = session.data?.user.role;
  const items = ADMIN_NAV.filter((item) => role && item.roles.includes(role));

  return (
    <div className="flex h-full">
      <nav className="w-52 shrink-0 space-y-1 border-r border-line bg-surface-1 p-3" aria-label="管理导航">
        <p className="flex items-center gap-2 px-2 pb-2 pt-1 text-xs font-semibold text-ink-muted">
          <Activity className="size-3.5" aria-hidden />
          管理后台
        </p>
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end ?? false}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-control px-3 py-2 text-sm transition-colors",
                isActive ? "bg-brand-selected font-medium text-brand" : "text-ink-2 hover:bg-surface-hover hover:text-ink-1",
              )
            }
          >
            <item.icon className="size-4" aria-hidden />
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="min-w-0 flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
