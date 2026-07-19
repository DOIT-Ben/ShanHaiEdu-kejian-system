import type { Meta, StoryObj } from "@storybook/react-vite";
import { workflowStatuses } from "@/entities/workflow/model";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const meta = {
  title: "基础组件/任务状态",
  component: StatusBadge,
  args: { status: "review_required" },
  parameters: { layout: "centered" },
} satisfies Meta<typeof StatusBadge>;

export default meta;
type Story = StoryObj<typeof meta>;

export const WaitingForTeacher: Story = {};
export const Stale: Story = { args: { status: "stale" } };
export const Unknown: Story = { args: { status: "unknown" } };
export const AllStatuses: Story = {
  render: () => (
    <div className="flex max-w-2xl flex-wrap gap-3">
      {workflowStatuses.map((status) => (
        <StatusBadge key={status} status={status} />
      ))}
      <StatusBadge status="unknown" />
    </div>
  ),
};
