import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "./button";

const meta: Meta<typeof Button> = {
  title: "基础/Button",
  component: Button,
  args: { children: "开始生成" },
};
export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {};
export const Secondary: Story = { args: { variant: "secondary", children: "重新生成" } };
export const Outline: Story = { args: { variant: "outline", children: "查看版本" } };
export const Ghost: Story = { args: { variant: "ghost", children: "跳过" } };
export const Destructive: Story = { args: { variant: "destructive", children: "永久删除" } };
export const Loading: Story = { args: { loading: true, children: "生成中" } };
export const Disabled: Story = { args: { disabled: true, children: "先保存输入" } };
export const Small: Story = { args: { size: "sm", children: "重试" } };
