import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import {
  ProjectEntryForm,
  type ProjectEntryField,
  type ProjectEntryValues,
} from "@/features/projects/components/ProjectEntryForm";
import {
  ProjectEntryFrame,
  type ProjectSourceMode,
} from "@/features/projects/components/ProjectEntryFrame";

const modeOptions = [
  { detail: "每一步都由你确认", label: "边看边确认", value: "guided" },
  { detail: "可随时暂停并回来检查", label: "自动推进", value: "automatic" },
] as const;

function ProjectEntryPreview({
  initialMode,
  showErrors = false,
}: {
  initialMode: ProjectSourceMode;
  showErrors?: boolean;
}) {
  const [sourceMode, setSourceMode] = useState(initialMode);
  const [values, setValues] = useState<ProjectEntryValues>({
    executionMode: "guided",
    grade: "六年级",
    knowledgePoint: "百分数的意义",
    textbookEdition: initialMode === "anchor" ? "" : "人教版",
    title: "认识百分数",
  });
  const setField = (field: ProjectEntryField, value: string) =>
    setValues((current) => ({ ...current, [field]: value }));

  return (
    <ProjectEntryFrame onSourceModeChange={setSourceMode} sourceMode={sourceMode}>
      <ProjectEntryForm
        allowUnspecifiedTextbookEdition
        anchorSummary={`${values.grade} · ${values.textbookEdition || "未指定教材版本"} · ${values.knowledgePoint}`}
        busy={false}
        errors={showErrors ? { knowledgePoint: "请输入知识点", title: "请输入项目名称" } : {}}
        file={null}
        modeOptions={modeOptions}
        onFieldChange={setField}
        onFileChange={() => undefined}
        onSubmit={(event) => event.preventDefault()}
        sourceMode={sourceMode}
        submitLabel={sourceMode === "textbook" ? "创建项目并检查教材" : "创建课程项目"}
        values={values}
      />
    </ProjectEntryFrame>
  );
}

const meta = {
  title: "项目/创建入口",
  component: ProjectEntryFrame,
  tags: ["core-viewport"],
  args: {
    children: null,
    disabled: false,
    onSourceModeChange: () => undefined,
    sourceMode: "textbook",
  },
  render: () => <ProjectEntryPreview initialMode="textbook" />,
} satisfies Meta<typeof ProjectEntryFrame>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Textbook: Story = {};
export const AnchorOnly: Story = {
  render: () => <ProjectEntryPreview initialMode="anchor" />,
};
export const ValidationError: Story = {
  render: () => <ProjectEntryPreview initialMode="textbook" showErrors />,
};
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
