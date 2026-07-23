import type { Meta, StoryObj } from "@storybook/react-vite";
import type { LessonDto } from "@/features/lessons/api/lessonsApi";
import { LessonCollectionEditor } from "@/features/lessons/components/LessonCollectionEditor";

const lesson = {
  branches: [
    { branch_key: "lesson_plan", enabled: true, settings: {}, workflow_status: "not_ready" },
    { branch_key: "intro_options", enabled: true, settings: {}, workflow_status: "not_ready" },
    { branch_key: "ppt", enabled: true, settings: {}, workflow_status: "not_ready" },
    { branch_key: "video", enabled: false, settings: {}, workflow_status: "disabled" },
  ],
  created_at: "2026-07-22T02:00:00Z",
  estimated_minutes: 40,
  id: "20000000-0000-4000-8000-000000000001",
  lesson_key: "lesson-01",
  lock_version: 3,
  objective_summary: "能解释百分数表示一个数是另一个数的百分之几。",
  position: 1,
  project_id: "20000000-0000-4000-8000-000000000002",
  scope_summary: "借助百格图和果汁标签理解百分数的意义。",
  source_division_version_id: "20000000-0000-4000-8000-000000000003",
  status: "active",
  title: "第 1 课时 · 百分数的意义",
  updated_at: "2026-07-22T02:10:00Z",
} satisfies LessonDto;

const meta = {
  title: "Runtime/课时集合编辑",
  component: LessonCollectionEditor,
  tags: ["core-viewport"],
  args: {
    collectionEtag: 'W/"3"',
    lessonEtags: { [lesson.id]: 'W/"3"' },
    lessons: [lesson],
    onSaveBranches: () => undefined,
    onSaveCollection: () => undefined,
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-4xl p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof LessonCollectionEditor>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Ready: Story = {};
export const Empty: Story = { args: { lessons: [] } };
export const Conflict: Story = {
  args: { conflictMessage: "课时集合已被其他编辑者更新，请刷新后重新应用本次修改。" },
};
export const Saving: Story = {
  args: {
    disabled: true,
    savingCollection: true,
    savingLessonId: lesson.id,
  },
};
