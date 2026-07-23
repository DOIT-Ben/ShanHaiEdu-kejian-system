import type { Meta, StoryObj } from "@storybook/react-vite";
import { ProjectLessonGrid } from "@/features/projects/components/ProjectOverviewContent";

const lessons = [
  {
    branches: [
      { enabled: true, key: "lesson-plan", label: "教案", to: "/app" },
      { enabled: true, key: "intro", label: "课堂导入", to: "/app" },
      { enabled: false, key: "ppt", label: "课堂 PPT", to: "/app" },
    ],
    durationMinutes: 40,
    id: "lesson-1",
    scope: "借助百格图理解百分数表示一个数是另一个数的百分之几。",
    title: "第 1 课时 · 百分数的意义",
  },
];

const meta = {
  title: "项目/课时概览",
  component: ProjectLessonGrid,
  tags: ["core-viewport"],
  args: { lessons },
} satisfies Meta<typeof ProjectLessonGrid>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};
export const Loading: Story = { args: { lessons: [], loading: true } };
export const Empty: Story = { args: { lessons: [] } };
export const ErrorState: Story = {
  args: {
    errorMessage: "课时暂时无法读取，请检查网络后重试。",
    lessons: [],
    onRetry: () => undefined,
  },
};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
