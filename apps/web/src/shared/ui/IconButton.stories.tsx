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
export const Disabled: Story = { args: { disabled: true, label: "设置暂不可用" } };
