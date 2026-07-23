import type { Meta, StoryObj } from "@storybook/react-vite";
import { WorkbenchStatusBoard } from "@/features/workbench/components/WorkbenchStatusBoard";

const meta = {
  title: "工作台/制作进度板",
  component: WorkbenchStatusBoard,
  tags: ["core-viewport"],
  args: {
    items: [
      { id: "plan", status: "succeeded", title: "教案" },
      { id: "video", status: "running", title: "课堂视频", detail: "正在处理画面与字幕" },
    ],
  },
} satisfies Meta<typeof WorkbenchStatusBoard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const CompleteAndRunning: Story = {};
export const Empty: Story = { args: { items: [] } };
export const Loading: Story = { args: { state: "loading" } };
export const Error: Story = { args: { state: "error" } };
export const PartialSuccess: Story = {
  args: {
    items: [
      { id: "plan", status: "succeeded", title: "教案" },
      { id: "ppt", status: "failed", title: "课堂 PPT", detail: "需要重新确认设计稿" },
    ],
  },
};
