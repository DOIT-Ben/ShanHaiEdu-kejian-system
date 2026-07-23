import type { Meta, StoryObj } from "@storybook/react-vite";
import { LessonWorkbenchSummary } from "@/features/workbench/components/LessonWorkbenchSummary";

const meta = {
  title: "工作台/课时总览",
  component: LessonWorkbenchSummary,
  tags: ["core-viewport"],
  args: {
    branches: [
      { enabled: true, key: "lesson_plan", label: "教案", to: "/app" },
      { enabled: true, key: "intro_options", label: "课堂导入", to: "/app" },
      { enabled: false, key: "ppt", label: "课堂 PPT", to: "/app" },
      { enabled: true, key: "video", label: "课堂视频", to: "/app" },
    ],
    currentBranchKey: "lesson_plan",
    durationLabel: "40 分钟",
    lessonTitle: "第 1 课时 · 百分数的意义",
    objective: "能读写常见百分数并说明它与整体的关系。",
    statuses: [
      { id: "plan", status: "succeeded", title: "教案" },
      { id: "intro", status: "running", title: "课堂导入" },
      { id: "video", status: "paused", title: "课堂视频" },
    ],
  },
} satisfies Meta<typeof LessonWorkbenchSummary>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Active: Story = {};
export const Empty: Story = { args: { statuses: [] } };
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
