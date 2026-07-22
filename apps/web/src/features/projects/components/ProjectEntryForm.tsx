import { BookOpen, CheckCircle2, FileText, Upload, X } from "lucide-react";
import type { RefObject, SubmitEventHandler } from "react";
import type { ProjectSourceMode } from "@/features/projects/components/ProjectEntryFrame";
import { Button } from "@/shared/ui/Button";
import { Select } from "@/shared/ui/Select";

export type ProjectEntryValues = {
  executionMode: string;
  grade: string;
  knowledgePoint: string;
  textbookEdition: string;
  title: string;
};

export type ProjectEntryField = keyof ProjectEntryValues;

type ProjectEntryFormProps = {
  anchorSummary: string;
  busy: boolean;
  disabled?: boolean;
  errors?: Partial<Record<"knowledgePoint" | "title", string>>;
  file: File | null;
  fileError?: string;
  message?: string;
  modeOptions: readonly { detail?: string; label: string; value: string }[];
  onFieldChange: (field: ProjectEntryField, value: string) => void;
  onFileChange: (file: File | null) => void;
  onSubmit: SubmitEventHandler<HTMLFormElement>;
  recoveredFileName?: string;
  sourceMode: ProjectSourceMode;
  submitDisabled?: boolean;
  submitLabel: string;
  uploadSectionRef?: RefObject<HTMLElement | null>;
  values: ProjectEntryValues;
};

const grades = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"];
const textbookEditions = ["人教版", "北师大版", "苏教版", "冀教版"];
const inputClass =
  "mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 text-sm text-[var(--sh-ink-strong)] outline-none transition focus:border-[var(--sh-brand-300)] focus:shadow-[var(--sh-shadow-focus)]";

export function ProjectEntryForm({
  anchorSummary,
  busy,
  disabled = false,
  errors = {},
  file,
  fileError,
  message,
  modeOptions,
  onFieldChange,
  onFileChange,
  onSubmit,
  recoveredFileName,
  sourceMode,
  submitDisabled = false,
  submitLabel,
  uploadSectionRef,
  values,
}: ProjectEntryFormProps) {
  const unavailable = busy || disabled;

  return (
    <form
      aria-busy={busy}
      className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]"
      onSubmit={onSubmit}
    >
      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
        <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
          <BookOpen aria-hidden="true" className="size-5" />
          <h2 className="font-semibold">这节课讲什么</h2>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="text-sm font-medium text-[var(--sh-ink-default)]">
            项目名称
            <input
              aria-invalid={Boolean(errors.title)}
              className={inputClass}
              disabled={unavailable}
              onChange={(event) => onFieldChange("title", event.target.value)}
              placeholder="例如：认识百分数"
              value={values.title}
            />
            {errors.title ? (
              <span className="mt-1 block text-xs text-[var(--sh-danger)]">{errors.title}</span>
            ) : null}
          </label>
          <label className="text-sm font-medium text-[var(--sh-ink-default)]">
            知识点
            <input
              aria-invalid={Boolean(errors.knowledgePoint)}
              className={inputClass}
              disabled={unavailable}
              onChange={(event) => onFieldChange("knowledgePoint", event.target.value)}
              placeholder="例如：百分数的意义"
              value={values.knowledgePoint}
            />
            {errors.knowledgePoint ? (
              <span className="mt-1 block text-xs text-[var(--sh-danger)]">
                {errors.knowledgePoint}
              </span>
            ) : null}
          </label>
          <label className="text-sm font-medium text-[var(--sh-ink-default)]">
            年级
            <Select
              ariaLabel="年级"
              className="mt-2 w-full"
              disabled={unavailable}
              onValueChange={(value) => onFieldChange("grade", value)}
              options={grades.map((value) => ({ label: value, value }))}
              value={values.grade}
            />
          </label>
          <label className="text-sm font-medium text-[var(--sh-ink-default)]">
            教材版本
            <Select
              ariaLabel="教材版本"
              className="mt-2 w-full"
              disabled={unavailable}
              onValueChange={(value) => onFieldChange("textbookEdition", value)}
              options={textbookEditions.map((value) => ({ label: value, value }))}
              value={values.textbookEdition}
            />
          </label>
        </div>
        <fieldset className="mt-4" disabled={unavailable}>
          <legend className="text-sm font-medium text-[var(--sh-ink-default)]">我想怎么推进</legend>
          <div
            className={`mt-2 grid gap-2 ${modeOptions.length > 2 ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}
          >
            {modeOptions.map((option) => (
              <label
                className="cursor-pointer rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] p-2.5 has-[:checked]:border-[var(--sh-brand-500)] has-[:checked]:bg-[var(--sh-brand-50)]"
                key={option.value}
              >
                <input
                  checked={values.executionMode === option.value}
                  className="sr-only"
                  name="project-execution-mode"
                  onChange={() => onFieldChange("executionMode", option.value)}
                  type="radio"
                />
                <span className="block text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {option.label}
                </span>
                {option.detail ? (
                  <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">
                    {option.detail}
                  </span>
                ) : null}
              </label>
            ))}
          </div>
        </fieldset>
      </section>

      <section
        className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]"
        id="textbook-upload-step"
        ref={uploadSectionRef}
      >
        <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
          <FileText aria-hidden="true" className="size-5" />
          <h2 className="font-semibold">{sourceMode === "textbook" ? "教材文件" : "课程范围"}</h2>
        </div>
        {sourceMode === "textbook" ? (
          file ? (
            <div className="mt-4 rounded-[var(--sh-radius-sm)] border border-[var(--sh-success)] bg-[var(--sh-success-soft)] p-4">
              <div className="flex items-center gap-3">
                <CheckCircle2 aria-hidden="true" className="size-5 text-[var(--sh-success)]" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {file.name}
                  </p>
                  <p className="text-xs text-[var(--sh-ink-muted)]">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
                <button
                  aria-label="移除教材文件"
                  className="grid size-9 place-items-center rounded-md hover:bg-[var(--sh-surface-elevated)]"
                  disabled={unavailable}
                  onClick={() => onFileChange(null)}
                  type="button"
                >
                  <X aria-hidden="true" className="size-4" />
                </button>
              </div>
            </div>
          ) : (
            <label
              className="mt-4 grid min-h-40 cursor-pointer place-items-center rounded-[var(--sh-radius-md)] border border-dashed border-[var(--sh-brand-300)] bg-[var(--sh-brand-50)] p-5 text-center hover:border-[var(--sh-brand-500)]"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                onFileChange(event.dataTransfer.files[0] ?? null);
              }}
            >
              <input
                accept="application/pdf"
                className="sr-only"
                disabled={unavailable}
                onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
                type="file"
              />
              <span>
                <Upload aria-hidden="true" className="mx-auto size-7 text-[var(--sh-brand-600)]" />
                <span className="mt-2 block text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {recoveredFileName ? "重新选择同一份 PDF" : "选择 PDF 教材"}
                </span>
                <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">
                  单个文件不超过 100 MB
                </span>
              </span>
            </label>
          )
        ) : (
          <div
            aria-label="课程锚点摘要"
            className="mt-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-soft)] px-4 py-4"
            role="region"
          >
            <p className="text-xs font-medium text-[var(--sh-ink-faint)]">课程范围</p>
            <p className="mt-2 text-sm font-semibold leading-6 text-[var(--sh-ink-strong)]">
              {anchorSummary}
            </p>
            <p className="mt-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
              创建后直接进入项目，不会建立教材上传或解析任务。
            </p>
          </div>
        )}
        {fileError ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" id="textbook-file-error" role="alert">
            {fileError}
          </p>
        ) : null}
        {message ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {message}
          </p>
        ) : null}
        <Button
          className="mt-4 w-full"
          disabled={unavailable || submitDisabled}
          size="lg"
          type="submit"
        >
          {submitLabel}
        </Button>
      </section>
    </form>
  );
}
