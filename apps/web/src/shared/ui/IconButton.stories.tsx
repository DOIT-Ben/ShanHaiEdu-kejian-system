import type { Meta, StoryObj } from "@storybook/react-vite";
import { Settings } from "lucide-react";
import { IconButton } from "@/shared/ui/IconButton";

const meta = {
  title: "基础组件/图标按钮",
  component: IconButton,
  args: { children: <Settings aria-hidden="true" />, label: "创作设置" },
  parameters: { layout: "centered" },
} satisfies Meta<typeof IconButton>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
export const Primary: Story = { args: { label: "发送", variant: "primary" } };
export const Disabled: Story = { args: { disabled: true, label: "设置暂不可用" } };
export const Focused: Story = { args: { autoFocus: true, label: "键盘焦点" } };
export const Pressed: Story = { args: { "aria-pressed": true, label: "按下状态" } };
export const Loading: Story = {
  args: { label: "发送", loading: true, loadingText: "正在发送", variant: "primary" },
};
export const Success: Story = {
  args: { label: "发送", success: true, successText: "发送成功", variant: "primary" },
};
export const Error: Story = {
  args: { error: true, errorText: "发送失败", label: "发送", variant: "primary" },
};
