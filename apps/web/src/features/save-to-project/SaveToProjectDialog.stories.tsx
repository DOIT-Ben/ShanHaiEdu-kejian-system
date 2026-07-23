import type { Meta, StoryObj } from "@storybook/react-vite";
import { type SaveSlot, SaveToProjectDialog } from "@/features/save-to-project/SaveToProjectDialog";

const projects = [
  { id: "project-1", title: "认识百分数" },
  { id: "project-2", title: "分数与小数" },
];

const slots = [
  { accepts: ["image"], key: "cover_image", label: "项目封面" },
  { accepts: ["image", "ppt_page"], key: "ppt_body", label: "PPT 正文素材" },
] satisfies SaveSlot[];

const meta = {
  title: "业务组件/保存到项目",
  component: SaveToProjectDialog,
  tags: ["core-viewport"],
  args: {
    onOpenChange: () => undefined,
    onSave: () => undefined,
    open: true,
    projects,
    result: { id: "story-image-1", title: "果汁标签观察图", type: "image" },
    slots,
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

export const SaveConflict: Story = {
  args: {
    conflict: { canAppend: true, message: "PPT 正文素材已有当前版本" },
    sourceProjectId: "project-1",
  },
};

export const Busy: Story = { args: { busy: true } };

export const Error: Story = {
  args: { errorMessage: "保存没有完成，请刷新目标项目后重试。" },
};

export const NoCompatibleSlot: Story = {
  args: {
    result: { id: "story-video-1", title: "百分数课堂短片", type: "video" },
  },
};
