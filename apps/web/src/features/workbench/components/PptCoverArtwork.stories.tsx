import type { Meta, StoryObj } from "@storybook/react-vite";
import { PptCoverArtwork } from "@/features/workbench/components/PptCoverArtwork";

const meta = {
  title: "PPT/封面预览",
  component: PptCoverArtwork,
  args: {
    children: (
      <>
        <p className="text-sm font-medium">六年级数学</p>
        <h2 className="mt-2 text-3xl font-semibold">认识百分数</h2>
      </>
    ),
    demo: true,
    variant: 1,
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-[760px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PptCoverArtwork>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ClassroomArtwork: Story = {};
export const GeneratedPlaceholder: Story = { args: { demo: false, variant: 2 } };
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
