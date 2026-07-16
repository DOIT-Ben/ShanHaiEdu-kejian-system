import { NavLink, Outlet } from "react-router";
import { cn } from "@/shared/lib/cn";

const GATEWAY_TABS = [
  { to: "providers", label: "Provider" },
  { to: "models", label: "能力与模型" },
  { to: "routes", label: "路由策略" },
  { to: "budgets", label: "预算与配额" },
  { to: "runs", label: "运行记录" },
];

/** 模型网关分区：二级页签导航。 */
export function AdminGatewayLayout() {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <nav className="flex gap-1 border-b border-line bg-surface-1 px-6 pt-3" aria-label="模型网关导航">
        {GATEWAY_TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              cn(
                "rounded-t-control border-b-2 px-3 py-2 text-sm transition-colors",
                isActive
                  ? "border-brand font-medium text-brand"
                  : "border-transparent text-ink-2 hover:bg-surface-hover hover:text-ink-1",
              )
            }
          >
            {tab.label}
          </NavLink>
        ))}
      </nav>
      <div className="min-h-0 flex-1 overflow-auto">
        <Outlet />
      </div>
    </div>
  );
}
