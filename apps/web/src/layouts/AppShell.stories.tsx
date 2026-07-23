import type { Meta, StoryObj } from "@storybook/react-vite";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/layouts/AppShell";

function ShellPreview() {
  return (
    <Routes>
      <Route
        element={
          <AppShell
            accountInitial="林"
            accountLabel="林老师 · 教师"
            notifications={[
              { detail: "第 1 课时等待确认", title: "教案已准备好", to: "/app/tasks" },
            ]}
            searchEntries={[{ detail: "项目", label: "认识百分数", to: "/app/projects/project-1" }]}
          />
        }
        path="/"
      >
        <Route
          index
          element={
            <div className="mx-auto max-w-5xl px-5 py-8">
              <h1 className="text-2xl font-semibold text-[var(--sh-ink-strong)]">今天的课堂作品</h1>
              <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">继续完成认识百分数。</p>
            </div>
          }
        />
      </Route>
    </Routes>
  );
}

const meta = {
  title: "全局布局/应用壳",
  component: AppShell,
  tags: ["core-viewport"],
  parameters: { layout: "fullscreen" },
  render: () => <ShellPreview />,
} satisfies Meta<typeof AppShell>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Desktop: Story = {};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
