import type { Meta, StoryObj } from "@storybook/react-vite";
import { ProjectRow } from "@/features/projects/components/ProjectRow";

const project = {
  currentLesson: "第 1 课时 · 百分数的意义",
  grade: "六年级",
  id: "project-1",
  knowledgePoint: "百分数的意义",
  nextAction: "确认第 1 课时教案",
  status: "active" as const,
  textbookEdition: "人教版",
  title: "认识百分数",
  updatedAt: "刚刚",
};

const meta = {
  title: "项目/项目行",
  component: ProjectRow,
  tags: ["core-viewport"],
  args: { project },
} satisfies Meta<typeof ProjectRow>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Active: Story = {};
export const Draft: Story = { args: { project: { ...project, status: "draft" } } };
export const Archived: Story = {
  args: { project: { ...project, archived: true, status: "archived" } },
};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
