import type { Meta, StoryObj } from "@storybook/react-vite";
import { BookOpen, Plus } from "lucide-react";
import { Button } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";

const meta = {
  title: "基础组件/空状态",
  component: EmptyState,
  args: {
    description: "添加教材后，系统会帮助你整理课时并生成完整教案。",
    icon: BookOpen,
    title: "还没有课堂项目",
  },
} satisfies Meta<typeof EmptyState>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Informational: Story = {};
export const WithNextAction: Story = {
  args: {
    action: (
      <Button>
        <Plus aria-hidden="true" />
        新建课堂项目
      </Button>
    ),
  },
};
