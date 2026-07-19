import type { Meta, StoryObj } from "@storybook/react-vite";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const meta = {
  title: "基础组件/聚焦页面标题",
  component: FocusPageHeader,
  args: { title: "认识百分数" },
} satisfies Meta<typeof FocusPageHeader>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Basic: Story = {};
export const GuidedAction: Story = {
  args: {
    action: <Button>确认教案并继续</Button>,
    description: "逐段检查并直接修改。确认后即可继续制作课堂课件。",
    eyebrow: "当前要做：修改并确认第 1 课时教案",
    status: <StatusBadge status="review_required" />,
  },
};

export const WithSupportingControl: Story = {
  args: {
    action: <Button>创建项目</Button>,
    description: "课时、教案和课堂作品都保留在这里。",
    supporting: (
      <input
        aria-label="搜索项目"
        className="min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 text-sm"
        placeholder="搜索项目或知识点"
        type="search"
      />
    ),
    title: "我的项目",
  },
};
