import type { Meta, StoryObj } from "@storybook/react-vite";
import { ContentDefinitionRenderer } from "@/features/content-definition/ContentDefinitionRenderer";
import { lessonPlanData, lessonPlanDefinition } from "@/features/content-definition/fixtures";
import type { ContentDefinition } from "@/features/content-definition/model";

const compactDefinition: ContentDefinition = {
  definition_key: "primary_math.compact_plan",
  title: "简要课堂方案",
  fields: [
    {
      field_key: "goal",
      label: "本课目标",
      type: "text",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "questions",
      label: "关键问题",
      type: "list",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "minutes",
      label: "预计时长",
      type: "number",
      required: true,
      editable: true,
      deletable: false,
    },
    {
      field_key: "extension",
      label: "扩展内容",
      type: "future_widget",
      required: false,
      editable: false,
      deletable: false,
    },
  ],
};

const meta = {
  title: "业务组件/动态内容渲染器",
  component: ContentDefinitionRenderer,
  args: { definition: lessonPlanDefinition, data: lessonPlanData },
} satisfies Meta<typeof ContentDefinitionRenderer>;

export default meta;
type Story = StoryObj<typeof meta>;

export const DefaultLessonPlan: Story = {
  decorators: [
    (Story) => (
      <article className="mx-auto max-w-4xl rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] px-8">
        <Story />
      </article>
    ),
  ],
};
export const AlternateSchema: Story = {
  args: {
    definition: compactDefinition,
    data: { goal: "理解整体与部分的关系", questions: ["百分数表示什么？"], minutes: 40 },
  },
  decorators: [
    (Story) => (
      <article className="mx-auto max-w-3xl rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] px-8">
        <Story />
      </article>
    ),
  ],
};
