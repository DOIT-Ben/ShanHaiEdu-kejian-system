import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  CreationResultUnavailableNotice,
  CreationSessionBoundaryNotice,
} from "@/features/creation-studio/CreationSessionOutcome";

const meta = {
  title: "创作台/运行时边界",
  component: CreationResultUnavailableNotice,
  tags: ["core-viewport"],
} satisfies Meta<typeof CreationResultUnavailableNotice>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Completed: Story = {};

export const SessionOnly: Story = {
  render: () => <CreationSessionBoundaryNotice />,
};

export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
