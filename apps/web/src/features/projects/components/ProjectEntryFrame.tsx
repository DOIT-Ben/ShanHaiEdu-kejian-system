import type { ReactNode } from "react";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export type ProjectSourceMode = "textbook" | "anchor";

type ProjectEntryFrameProps = {
  children: ReactNode;
  description?: string;
  eyebrow?: string;
  onSourceModeChange: (mode: ProjectSourceMode) => void;
  sourceMode: ProjectSourceMode;
  title?: string;
};

const sourceOptions: ReadonlyArray<{
  detail: string;
  label: string;
  value: ProjectSourceMode;
}> = [
  { detail: "上传教材并进入解析流程", label: "使用 PDF 教材", value: "textbook" },
  { detail: "用年级、版本和知识点限定课程范围", label: "暂不使用教材", value: "anchor" },
];

export function ProjectEntryFrame({
  children,
  description = "先确定课程范围；有教材时上传 PDF，没有教材时可直接用课程锚点创建。",
  eyebrow,
  onSourceModeChange,
  sourceMode,
  title = "新建课堂项目",
}: ProjectEntryFrameProps) {
  return (
    <div className="mx-auto max-w-[1120px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader description={description} eyebrow={eyebrow} title={title} />
      <fieldset className="mt-5">
        <legend className="text-sm font-semibold text-[var(--sh-ink-strong)]">课程内容来源</legend>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {sourceOptions.map((option) => {
            const selected = sourceMode === option.value;
            return (
              <label
                className={`flex cursor-pointer items-start gap-3 rounded-[var(--sh-radius-md)] border px-4 py-3 transition-colors ${selected ? "border-[var(--sh-action-primary)] bg-[var(--sh-brand-50)]" : "border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] hover:bg-[var(--sh-surface-soft)]"}`}
                key={option.value}
              >
                <input
                  checked={selected}
                  className="mt-1 size-4 accent-[var(--sh-action-primary)]"
                  name="project-source-mode"
                  onChange={() => onSourceModeChange(option.value)}
                  type="radio"
                  value={option.value}
                />
                <span>
                  <span className="block text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {option.label}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-[var(--sh-ink-muted)]">
                    {option.detail}
                  </span>
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      {children}
    </div>
  );
}
