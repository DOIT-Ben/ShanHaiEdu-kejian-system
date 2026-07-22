import { ChevronRight, FolderOpen } from "lucide-react";
import { useEffect, useRef } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { useMockRuntime } from "@/shared/api/mockClient";
import { cn } from "@/shared/lib/cn";

const tabs = [
  { label: "项目总览", path: "" },
  { label: "教材与课时", path: "materials" },
  { label: "课时工作台", path: "lessons" },
  { label: "素材与成果", path: "results" },
  { label: "项目任务", path: "tasks" },
  { label: "项目交付", path: "delivery" },
];

export function ProjectOverviewLayout() {
  const { projectId = "" } = useParams();
  const location = useLocation();
  const navRef = useRef<HTMLElement>(null);
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const base = `/app/projects/${projectId}`;

  useEffect(() => {
    navRef.current
      ?.querySelector<HTMLElement>('[aria-current="page"]')
      ?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [location.pathname]);

  return (
    <div className="min-h-[calc(100vh-var(--sh-topbar-height))] bg-[var(--sh-surface-warm)]">
      <div className="border-b border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)]">
        <div className="mx-auto flex min-h-12 max-w-[1600px] items-center gap-4 px-4 md:px-8">
          <div className="hidden min-w-0 max-w-[260px] shrink items-center gap-2 text-sm text-[var(--sh-ink-muted)] lg:flex xl:max-w-[360px]">
            <FolderOpen aria-hidden="true" className="size-4" />
            <NavLink className="hover:text-[var(--sh-ink-strong)]" to="/app/projects">
              项目
            </NavLink>
            <ChevronRight aria-hidden="true" className="size-4" />
            <span className="min-w-0 truncate text-[var(--sh-ink-strong)]">
              {project?.title ?? "项目"}
            </span>
          </div>
          <div className="relative min-w-0 flex-1">
            <nav
              aria-label="项目导航"
              className="flex gap-1 overflow-x-auto pr-8 [scrollbar-width:none] md:pr-0 [&::-webkit-scrollbar]:hidden"
              ref={navRef}
            >
              {tabs.map((tab) => {
                const to = tab.path ? `${base}/${tab.path}` : base;
                return (
                  <NavLink
                    className={({ isActive }) =>
                      cn(
                        "shrink-0 border-b-2 border-transparent px-3 py-3 text-sm font-medium text-[var(--sh-ink-muted)]",
                        isActive && "border-[var(--sh-brand-500)] text-[var(--sh-ink-strong)]",
                      )
                    }
                    end={!tab.path}
                    key={tab.path}
                    to={to}
                  >
                    {tab.label}
                  </NavLink>
                );
              })}
            </nav>
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-y-0 right-0 w-9 bg-gradient-to-l from-[var(--sh-surface-canvas)] via-[var(--sh-surface-canvas)]/90 to-transparent md:hidden"
            />
          </div>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
