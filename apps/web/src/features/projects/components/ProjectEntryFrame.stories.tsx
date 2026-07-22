import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import {
  ProjectEntryFrame,
  type ProjectSourceMode,
} from "@/features/projects/components/ProjectEntryFrame";

function ProjectEntryPreview({ initialMode }: { initialMode: ProjectSourceMode }) {
  const [sourceMode, setSourceMode] = useState(initialMode);
  return (
    <ProjectEntryFrame onSourceModeChange={setSourceMode} sourceMode={sourceMode}>
      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">这节课讲什么</h2>
          <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">六年级 · 人教版 · 百分数的意义</p>
        </section>
        <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">
            {sourceMode === "textbook" ? "教材文件" : "课程范围"}
          </h2>
          <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">
            {sourceMode === "textbook" ? "等待选择 PDF" : "不建立教材解析任务"}
          </p>
        </section>
      </div>
    </ProjectEntryFrame>
  );
}

const meta = {
  title: "项目/创建入口",
  component: ProjectEntryFrame,
  args: {
    children: null,
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
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
