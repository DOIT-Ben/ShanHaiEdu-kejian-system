import type { Meta, StoryObj } from "@storybook/react-vite";
import { CreationHomePage } from "@/pages/creation/CreationHomePage";

const meta = {
  title: "页面/创作中心",
  component: CreationHomePage,
  tags: ["core-viewport"],
  parameters: { layout: "fullscreen" },
} satisfies Meta<typeof CreationHomePage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Desktop: Story = {};
export const Tablet1024: Story = {
  parameters: { viewport: { defaultViewport: "tablet1024" } },
};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
