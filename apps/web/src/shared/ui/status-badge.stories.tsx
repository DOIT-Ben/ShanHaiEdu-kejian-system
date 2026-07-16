import type { Meta, StoryObj } from "@storybook/react";
import { Badge } from "./badge";
import { ArtifactStatusBadge, NodeStatusBadge, TaskStatusBadge } from "./status-badge";
import { NODE_STATUSES, TASK_STATUSES, ARTIFACT_STATUSES } from "@/shared/lib/status";

const meta: Meta<typeof Badge> = {
  title: "基础/状态徽标",
  component: Badge,
};
export default meta;
type Story = StoryObj<typeof Badge>;

export const Tones: Story = {
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Badge tone="neutral">中性</Badge>
      <Badge tone="brand">品牌</Badge>
      <Badge tone="success">成功</Badge>
      <Badge tone="warning">警告</Badge>
      <Badge tone="danger">危险</Badge>
      <Badge tone="running">进行中</Badge>
    </div>
  ),
};

export const NodeStatuses: Story = {
  render: () => (
    <div className="flex max-w-xl flex-wrap gap-2">
      {NODE_STATUSES.map((status) => (
        <NodeStatusBadge key={status} status={status} />
      ))}
    </div>
  ),
};

export const TaskStatuses: Story = {
  render: () => (
    <div className="flex max-w-xl flex-wrap gap-2">
      {TASK_STATUSES.map((status) => (
        <TaskStatusBadge key={status} status={status} />
      ))}
    </div>
  ),
};

export const ArtifactStatuses: Story = {
  render: () => (
    <div className="flex max-w-xl flex-wrap gap-2">
      {ARTIFACT_STATUSES.map((status) => (
        <ArtifactStatusBadge key={status} status={status} />
      ))}
    </div>
  ),
};
