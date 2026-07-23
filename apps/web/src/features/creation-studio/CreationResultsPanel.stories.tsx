import type { Meta, StoryObj } from "@storybook/react-vite";
import { CreationResultsPanel } from "@/features/creation-studio/CreationResultsPanel";

const meta = {
  title: "创作台/结果对话",
  component: CreationResultsPanel,
  tags: ["core-viewport"],
  args: {
    candidate: 0,
    candidateCount: 3,
    generation: 1,
    hasUnappliedChanges: false,
    onAdvance: () => undefined,
    onCandidateChange: () => undefined,
    onDownload: () => undefined,
    prompt: "用清透插画表现果汁标签中的百分数。",
    ratio: "16:9",
    stage: "ready",
    type: "image",
  },
} satisfies Meta<typeof CreationResultsPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};
export const Queued: Story = { args: { stage: "queued" } };
export const Running: Story = { args: { stage: "running" } };
export const Saved: Story = {
  args: { savedTarget: "认识百分数 · 第 1 课时", stage: "saved" },
};
export const Presentation: Story = {
  args: { candidateCount: 2, ratio: "16:9", type: "presentation" },
};
export const Video: Story = {
  args: { candidateCount: 3, ratio: "16:9", type: "video" },
};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
