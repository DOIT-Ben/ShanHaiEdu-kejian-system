import type { Meta, StoryObj } from "@storybook/react-vite";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";

const meta = {
  title: "视频/关键帧预览",
  component: VideoScenePreview,
  args: { topic: "百分数的意义", variant: 0 },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-[720px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof VideoScenePreview>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Standard: Story = {};
export const Compact: Story = { args: { compact: true } };
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
