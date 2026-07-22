import { BookOpen, FileText, Upload } from "lucide-react";
import type { SubmitEventHandler } from "react";
import { Controller, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";
import type { ProjectSourceMode } from "@/features/projects/components/ProjectEntryFrame";
import type { RuntimeNewProjectStage } from "@/pages/projects/runtimeNewProjectRecovery";
import { Button } from "@/shared/ui/Button";
import { Select } from "@/shared/ui/Select";

export type ProjectEntryFormValues = {
  executionMode: "guided" | "automatic";
  grade: string;
  knowledgePoint: string;
  sourceMode: ProjectSourceMode;
  textbookEdition: string;
  title: string;
};

type RuntimeProjectEntryFormProps = {
  anchorSummary: string;
  control: Control<ProjectEntryFormValues>;
  errors: FieldErrors<ProjectEntryFormValues>;
  file: File | null;
  message: string;
  onFileChange: (file: File | null) => void;
  onSubmit: SubmitEventHandler<HTMLFormElement>;
  recoveredFileName?: string;
  register: UseFormRegister<ProjectEntryFormValues>;
  sourceMode: ProjectSourceMode;
  stage: RuntimeNewProjectStage;
  submitting: boolean;
  writeReady: boolean;
};

const grades = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"];
const textbookEditions = ["人教版", "北师大版", "苏教版"];
const inputClass =
  "mt-1.5 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3 text-sm text-[var(--sh-ink-strong)] outline-none transition focus:border-[var(--sh-brand-300)] focus:shadow-[var(--sh-shadow-focus)]";

const stageLabels: Record<RuntimeNewProjectStage, string> = {
  checking: "正在核对教材",
  confirming: "正在建立课堂任务",
  creating: "正在创建课程",
  idle: "创建项目并上传教材",
  uploading: "正在上传教材",
};

export function RuntimeProjectEntryForm({
  anchorSummary,
  control,
  errors,
  file,
  message,
  onFileChange,
  onSubmit,
  recoveredFileName,
  register,
  sourceMode,
  stage,
  submitting,
  writeReady,
}: RuntimeProjectEntryFormProps) {
  return (
    <form
      aria-busy={submitting}
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
              className={inputClass}
              disabled={submitting}
              {...register("title")}
              placeholder="例如：认识百分数"
            />
            {errors.title ? (
              <span className="mt-1 block text-xs text-[var(--sh-danger)]">
                {errors.title.message}
              </span>
            ) : null}
          </label>
          <label className="text-sm font-medium text-[var(--sh-ink-default)]">
            知识点
            <input
              className={inputClass}
              disabled={submitting}
              {...register("knowledgePoint")}
              placeholder="例如：百分数的意义"
            />
            {errors.knowledgePoint ? (
              <span className="mt-1 block text-xs text-[var(--sh-danger)]">
                {errors.knowledgePoint.message}
              </span>
            ) : null}
          </label>
          <Controller
            control={control}
            name="grade"
            render={({ field }) => (
              <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                年级
                <Select
                  ariaLabel="选择年级"
                  className="mt-1.5 w-full"
                  disabled={submitting}
                  onValueChange={field.onChange}
                  options={grades.map((value) => ({ label: value, value }))}
                  value={field.value}
                />
              </label>
            )}
          />
          <Controller
            control={control}
            name="textbookEdition"
            render={({ field }) => (
              <label className="text-sm font-medium text-[var(--sh-ink-default)]">
                教材版本
                <Select
                  ariaLabel="选择教材版本"
                  className="mt-1.5 w-full"
                  disabled={submitting}
                  onValueChange={field.onChange}
                  options={textbookEditions.map((value) => ({ label: value, value }))}
                  value={field.value}
                />
              </label>
            )}
          />
        </div>
        <div className="mt-4">
          <p className="text-sm font-medium text-[var(--sh-ink-default)]">制作方式</p>
          <Controller
            control={control}
            name="executionMode"
            render={({ field }) => (
              <Select
                ariaLabel="选择制作方式"
                className="mt-1.5 w-full sm:w-72"
                disabled={submitting}
                onValueChange={field.onChange}
                options={[
                  { label: "边看边确认", value: "guided" },
                  { label: "自动完成可执行步骤", value: "automatic" },
                ]}
                value={field.value}
              />
            )}
          />
        </div>
      </section>

      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
        <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
          <FileText aria-hidden="true" className="size-5" />
          <h2 className="font-semibold">
            {sourceMode === "textbook" ? "上传教材" : "确认课程范围"}
          </h2>
        </div>
        {sourceMode === "textbook" ? (
          <label className="mt-4 grid min-h-40 cursor-pointer place-items-center rounded-[var(--sh-radius-md)] border border-dashed border-[var(--sh-brand-300)] bg-[var(--sh-brand-50)] p-5 text-center hover:border-[var(--sh-brand-500)]">
            <input
              accept="application/pdf"
              className="sr-only"
              disabled={submitting}
              onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
              type="file"
            />
            <span>
              <Upload aria-hidden="true" className="mx-auto size-7 text-[var(--sh-brand-600)]" />
              <span className="mt-2 block text-sm font-semibold text-[var(--sh-ink-strong)]">
                {file?.name ?? (recoveredFileName ? "重新选择同一份 PDF" : "选择 PDF 教材")}
              </span>
              <span className="mt-1 block text-xs text-[var(--sh-ink-muted)]">
                {file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "选择后会安全上传"}
              </span>
            </span>
          </label>
        ) : (
          <div
            aria-label="课程锚点摘要"
            className="mt-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-soft)] px-4 py-4"
            role="region"
          >
            <p className="text-xs font-medium text-[var(--sh-ink-faint)]">课程锚点</p>
            <p className="mt-2 text-sm font-semibold leading-6 text-[var(--sh-ink-strong)]">
              {anchorSummary}
            </p>
            <p className="mt-2 text-xs leading-5 text-[var(--sh-ink-muted)]">
              项目创建后将只使用以上课程范围；当前项目暂不能追加教材。
            </p>
          </div>
        )}
        {message ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {message}
          </p>
        ) : null}
        <Button className="mt-4 w-full" disabled={submitting || !writeReady} type="submit">
          {stage === "idle" && sourceMode === "textbook" ? <Upload aria-hidden="true" /> : null}
          {stage === "idle" && sourceMode === "anchor" ? "创建课程项目" : stageLabels[stage]}
        </Button>
        {!writeReady ? (
          <p className="mt-3 text-xs leading-5 text-[var(--sh-warning)]" role="status">
            暂时无法保存，请刷新页面后重试。
          </p>
        ) : null}
        <p className="mt-3 text-xs leading-5 text-[var(--sh-ink-faint)]">
          {sourceMode === "textbook"
            ? "上传完成后会进入教材解析，你可以随时回来查看进度。"
            : "项目创建后会直接进入课程空间。"}
        </p>
      </section>
    </form>
  );
}
