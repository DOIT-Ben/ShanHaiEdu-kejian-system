import { useNavigate } from "react-router-dom";
import type { SearchEntry } from "@/features/navigation/GlobalSearchDialog";
import type { NotificationItem } from "@/features/navigation/NotificationMenu";
import { AppShell } from "@/layouts/AppShell";
import { signOut, useMockSession } from "@/shared/auth/mockAuth";

const searchEntries: readonly SearchEntry[] = [
  { label: "认识百分数", detail: "项目", to: "/app/projects/01960000-0000-7000-8000-000000000001" },
  {
    label: "第 1 课时 · 百分数的意义",
    detail: "课时",
    to: "/app/projects/01960000-0000-7000-8000-000000000001/lessons/01960000-0000-7000-8000-000000000101/work/lesson-plan",
  },
  { label: "图片创作台", detail: "创作中心", to: "/app/creation/images" },
  { label: "视频创作台", detail: "创作中心", to: "/app/creation/videos" },
  { label: "PPT 创作台", detail: "创作中心", to: "/app/creation/presentations" },
  { label: "任务中心", detail: "任务", to: "/app/tasks" },
];

const notifications: readonly NotificationItem[] = [
  {
    title: "教案已完成检查",
    detail: "认识百分数 · 第 1 课时等待你确认",
    to: "/app/projects/01960000-0000-7000-8000-000000000001/lessons/01960000-0000-7000-8000-000000000101/work/lesson-plan",
  },
  {
    title: "1 张图片需要处理",
    detail: "已完成内容不受影响，只重新处理未完成内容",
    to: "/app/tasks",
  },
];

/**
 * Mock-only adapter. The visual shell itself is data-source agnostic; keeping
 * this session adapter at the development boundary prevents mock auth from
 * entering the real application bundle.
 */
export function GlobalAppShell() {
  const navigate = useNavigate();
  const session = useMockSession();
  const name = session?.user.name ?? "演示教师";
  return (
    <AppShell
      accountInitial={name.slice(0, 1)}
      accountLabel={`${name} · ${session?.user.role === "admin" ? "管理员" : "教师"}`}
      isAdmin={session?.user.role === "admin"}
      notifications={notifications}
      onSignOut={() => {
        signOut();
        void navigate("/login", { replace: true });
      }}
      searchEntries={searchEntries}
    />
  );
}
