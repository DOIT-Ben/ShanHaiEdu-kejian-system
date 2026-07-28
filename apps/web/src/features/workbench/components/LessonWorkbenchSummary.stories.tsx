import type { Meta, StoryObj } from "@storybook/react-vite";
import { LessonWorkbenchSummary } from "@/features/workbench/components/LessonWorkbenchSummary";

const meta = {
  title: "工作台/课时总览",
  component: LessonWorkbenchSummary,
  tags: ["core-viewport"],
  args: {
    branches: [
      { available: true, enabled: true, key: "lesson_plan", label: "教案", to: "/app" },
      {
        available: true,
        enabled: true,
        key: "intro_options",
        label: "课堂导入",
        to: "/app",
      },
      { available: false, enabled: false, key: "ppt", label: "课堂 PPT", to: "/app" },
      { available: false, enabled: false, key: "video", label: "课堂视频", to: "/app" },
    ],
    currentBranchKey: "lesson_plan",
    durationLabel: "40 分钟",
    objective: "能读写常见百分数并说明它与整体的关系。",
  },
} satisfies Meta<typeof LessonWorkbenchSummary>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Active: Story = {};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
