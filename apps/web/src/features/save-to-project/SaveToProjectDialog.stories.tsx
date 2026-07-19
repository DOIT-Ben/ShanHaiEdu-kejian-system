import type { Meta, StoryObj } from "@storybook/react-vite";
import { SaveToProjectDialog } from "@/features/save-to-project/SaveToProjectDialog";

const meta = {
  title: "业务组件/保存到项目",
  component: SaveToProjectDialog,
  args: {
    onOpenChange: () => undefined,
    onSaved: () => undefined,
    open: true,
    result: { id: "story-image-1", title: "果汁标签观察图", type: "image" },
  },
} satisfies Meta<typeof SaveToProjectDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ImageResult: Story = {};
export const LessonPresentationPage: Story = {
  args: {
    result: {
      id: "story-ppt-page-1",
      lessonLabel: "第 1 课时",
      title: "百分数百格图",
      type: "ppt_page",
    },
  },
};
