import type { Meta, StoryObj } from "@storybook/react-vite";
import { ArrowRight, Save } from "lucide-react";
import { Button } from "@/shared/ui/Button";

const meta = {
  title: "基础组件/按钮",
  component: Button,
  args: { children: "确认并继续" },
  parameters: { layout: "centered" },
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {};
export const Secondary: Story = { args: { variant: "secondary", children: "提出修改" } };
export const WithIcon: Story = {
  args: {
    children: (
      <>
        <Save aria-hidden="true" />
        保存修改
      </>
    ),
  },
};
export const LongChinese: Story = {
  args: {
    children: (
      <>
        采用这张封面并继续制作正文
        <ArrowRight aria-hidden="true" />
      </>
    ),
  },
};
export const Disabled: Story = { args: { disabled: true, children: "正在准备交付包" } };
export const Focused: Story = { args: { autoFocus: true, children: "键盘焦点" } };
export const Pressed: Story = {
  args: { "aria-pressed": true, children: "按下状态" },
};
export const Loading: Story = {
  args: { children: "保存修改", loading: true, loadingText: "正在保存" },
};
export const Success: Story = {
  args: { children: "保存修改", success: true, successText: "保存成功" },
};
export const Error: Story = {
  args: { children: "保存修改", error: true, errorText: "保存失败" },
};
