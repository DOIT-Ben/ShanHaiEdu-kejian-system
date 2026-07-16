import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router";
import {
  Bell,
  BookOpenCheck,
  ChevronsUpDown,
  FolderKanban,
  Home,
  LogOut,
  Settings2,
  Wifi,
  WifiOff,
} from "lucide-react";
import { useSession, useLogout } from "@/features/session";
import { useProjects } from "@/features/projects";
import { useMyTasks, taskTitle } from "@/features/tasks";
import { useConnectionStore } from "@/features/events";
import { cn } from "@/shared/lib/cn";
import { taskStatusMeta, isTaskActive, type TaskStatus } from "@/shared/lib/status";
import { ROLE_LABEL } from "@/shared/lib/format";
import {
  Badge,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Progress,
  Spinner,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/shared/ui";
import { ScenarioBadge } from "@/app/dev/ScenarioBadge";

function ConnectionIndicator() {
  const mode = useConnectionStore((s) => s.mode);
  const meta: Record<string, { label: string; className: string; icon: React.ReactNode }> = {
    connecting: { label: "连接中", className: "text-ink-muted", icon: <Spinner /> },
    sse: { label: "实时已连接", className: "text-success", icon: <Wifi className="size-4" aria-hidden /> },
    reconnecting: { label: "连接中断，正在重连", className: "text-warning", icon: <Wifi className="size-4" aria-hidden /> },
    polling: { label: "实时通道不可用，已切换为定时刷新", className: "text-warning", icon: <WifiOff className="size-4" aria-hidden /> },
    offline: { label: "未连接实时通道", className: "text-ink-muted", icon: <WifiOff className="size-4" aria-hidden /> },
  };
  const current = meta[mode] ?? meta.offline;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className={cn("inline-flex items-center gap-1.5 text-xs", current.className)}>
          {current.icon}
          <span className="hidden xl:inline">{current.label}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent>{current.label}</TooltipContent>
    </Tooltip>
  );
}

function TaskBell() {
  const navigate = useNavigate();
  const { projectId } = useParams();
  const tasks = useMyTasks();
  const active = (tasks.data ?? []).filter((t) => isTaskActive(t.status as TaskStatus));
  const failed = (tasks.data ?? []).filter((t) => t.status === "failed").slice(0, 3);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="relative flex size-9 items-center justify-center rounded-control text-ink-2 transition-colors hover:bg-surface-hover"
          aria-label={`任务通知（进行中 ${active.length} 个）`}
        >
          <Bell className="size-5" aria-hidden />
          {active.length > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-running text-[10px] font-semibold text-white">
              {active.length}
            </span>
          ) : null}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <DropdownMenuLabel>任务动态</DropdownMenuLabel>
        {active.length === 0 && failed.length === 0 ? (
          <p className="px-3 py-4 text-sm text-ink-muted">暂无进行中的任务。</p>
        ) : (
          <>
            {active.slice(0, 4).map((task) => (
              <div key={task.task_id} className="px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm text-ink-1">{taskTitle(task)}</span>
                  <Badge tone="running">{taskStatusMeta[task.status as TaskStatus]?.label ?? task.status}</Badge>
                </div>
                <Progress className="mt-1.5" value={task.progress_percent ?? 0} />
              </div>
            ))}
            {failed.map((task) => (
              <div key={task.task_id} className="flex items-center justify-between gap-2 px-3 py-2">
                <span className="truncate text-sm text-ink-1">{taskTitle(task)}</span>
                <Badge tone="danger">失败</Badge>
              </div>
            ))}
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => {
            void navigate(projectId ? `/app/projects/${projectId}/tasks` : "/app/projects");
          }}
        >
          查看任务中心
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function ProjectSwitcher() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const projects = useProjects({});
  if (!projectId) return null;
  const current = projects.data?.find((p) => p.project_id === projectId);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex max-w-64 items-center gap-2 rounded-control border border-line bg-surface-1 px-3 py-1.5 text-sm text-ink-1 transition-colors hover:bg-surface-hover"
        >
          <FolderKanban className="size-4 text-brand" aria-hidden />
          <span className="truncate">{current?.name ?? "选择项目"}</span>
          <ChevronsUpDown className="size-3.5 text-ink-muted" aria-hidden />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel>切换项目</DropdownMenuLabel>
        {(projects.data ?? []).map((project) => (
          <DropdownMenuItem
            key={project.project_id}
            onSelect={() => {
              void navigate(`/app/projects/${project.project_id}`);
            }}
          >
            <span className="truncate">{project.name}</span>
            {project.project_id === projectId ? <Badge tone="brand" className="ml-auto">当前</Badge> : null}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => {
            void navigate("/app/projects");
          }}
        >
          查看全部项目
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const session = useSession();
  const logout = useLogout();
  const navigate = useNavigate();
  const user = session.data?.user;
  if (!user) return null;
  const isAdmin = user.role !== "teacher";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-control px-2 py-1.5 transition-colors hover:bg-surface-hover"
          aria-label="用户菜单"
        >
          <span className="flex size-8 items-center justify-center rounded-full bg-brand-selected text-sm font-semibold text-brand">
            {user.display_name.slice(0, 1)}
          </span>
          <span className="hidden text-left md:block">
            <span className="block text-sm font-medium text-ink-1">{user.display_name}</span>
            <span className="block text-xs text-ink-muted">{ROLE_LABEL[user.role]}</span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          {user.display_name}
          <span className="mt-0.5 block text-xs font-normal text-ink-muted">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {isAdmin ? (
          <DropdownMenuItem
            onSelect={() => {
              void navigate("/admin");
            }}
          >
            <Settings2 className="size-4" aria-hidden />
            管理后台
          </DropdownMenuItem>
        ) : null}
        <DropdownMenuItem
          onSelect={() => {
            logout.mutate();
          }}
        >
          <LogOut className="size-4" aria-hidden />
          退出登录
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

const RAIL_ITEMS = [
  { to: "/app", label: "首页", icon: Home, end: true },
  { to: "/app/projects", label: "项目", icon: FolderKanban, end: false },
];

export function AppLayout() {
  const session = useSession();
  const isAdmin = session.data?.user.role !== "teacher";
  return (
    <div className="flex h-screen flex-col bg-page">
      <header className="flex h-16 shrink-0 items-center gap-4 border-b border-line bg-surface-1 px-4">
        <Link to="/app" className="flex items-center gap-2">
          <span className="flex size-9 items-center justify-center rounded-control bg-brand text-sm font-bold text-white">山</span>
          <span className="hidden text-base font-semibold text-ink-1 lg:block">山海教育课件系统</span>
        </Link>
        <ProjectSwitcher />
        <div className="ml-auto flex items-center gap-3">
          <ScenarioBadge />
          <ConnectionIndicator />
          <TaskBell />
          <UserMenu />
        </div>
      </header>
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[72px] shrink-0 flex-col items-center gap-1 border-r border-line bg-surface-1 py-3" aria-label="主导航">
          {RAIL_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex w-16 flex-col items-center gap-1 rounded-control py-2 text-xs transition-colors",
                  isActive ? "bg-brand-selected text-brand" : "text-ink-2 hover:bg-surface-hover hover:text-ink-1",
                )
              }
            >
              <item.icon className="size-5" aria-hidden />
              {item.label}
            </NavLink>
          ))}
          {isAdmin ? (
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                cn(
                  "mt-auto flex w-16 flex-col items-center gap-1 rounded-control py-2 text-xs transition-colors",
                  isActive ? "bg-brand-selected text-brand" : "text-ink-2 hover:bg-surface-hover hover:text-ink-1",
                )
              }
            >
              <BookOpenCheck className="size-5" aria-hidden />
              管理
            </NavLink>
          ) : null}
        </nav>
        <main className="min-w-0 flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
