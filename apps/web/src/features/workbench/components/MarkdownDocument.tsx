import { Check, Eye, FileText, PencilLine, Save } from "lucide-react";
import type { ReactNode } from "react";
import { useId } from "react";
import { MarkdownPreview } from "@/features/workbench/components/MarkdownPreview";
import { Button } from "@/shared/ui/Button";

export type DocumentMode = "edit" | "preview";

export function MarkdownDocument({
  ariaLabel,
  dirty,
  extraActions,
  markdown,
  mode,
  onChange,
  onModeChange,
  onSave,
  readOnly = false,
  title,
}: {
  ariaLabel: string;
  dirty: boolean;
  extraActions?: ReactNode;
  markdown: string;
  mode: DocumentMode;
  onChange: (markdown: string) => void;
  onModeChange: (mode: DocumentMode) => void;
  onSave: () => void;
  readOnly?: boolean;
  title: string;
}) {
  const editorId = useId();
  return (
    <section aria-label={title} className="mt-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-3 py-1.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="grid size-8 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
            <FileText aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">{title}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {extraActions}
          <div
            aria-label="稿件视图"
            className="inline-flex rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-1"
            role="group"
          >
            <button
              aria-pressed={mode === "preview"}
              className={`inline-flex min-h-8 items-center gap-1.5 rounded-[var(--sh-radius-sm)] px-3 text-sm font-medium ${mode === "preview" ? "bg-[var(--sh-surface-elevated)] text-[var(--sh-ink-strong)] shadow-[var(--sh-shadow-card)]" : "text-[var(--sh-ink-muted)]"}`}
              onClick={() => onModeChange("preview")}
              type="button"
            >
              <Eye aria-hidden="true" className="size-4" />
              预览
            </button>
            <button
              aria-pressed={mode === "edit"}
              className={`inline-flex min-h-8 items-center gap-1.5 rounded-[var(--sh-radius-sm)] px-3 text-sm font-medium ${mode === "edit" ? "bg-[var(--sh-surface-elevated)] text-[var(--sh-ink-strong)] shadow-[var(--sh-shadow-card)]" : "text-[var(--sh-ink-muted)]"}`}
              disabled={readOnly}
              onClick={() => onModeChange("edit")}
              type="button"
            >
              <PencilLine aria-hidden="true" className="size-4" />
              编辑
            </button>
          </div>
          {dirty ? (
            <Button onClick={onSave} size="sm">
              <Save aria-hidden="true" />
              保存修改
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1 text-xs text-[var(--sh-success)]">
              <Check aria-hidden="true" className="size-3.5" />
              已保存
            </span>
          )}
        </div>
      </div>
      {mode === "edit" ? (
        <label className="block" htmlFor={editorId}>
          <span className="sr-only">{ariaLabel}</span>
          <textarea
            aria-label={ariaLabel}
            className="min-h-[min(620px,calc(100dvh-280px))] w-full resize-y rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] px-5 py-6 font-mono text-[15px] leading-8 text-[var(--sh-ink-default)] shadow-[var(--sh-shadow-card)] outline-none transition-[border-color,box-shadow] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)] disabled:cursor-not-allowed disabled:opacity-70 md:px-12"
            disabled={readOnly}
            id={editorId}
            onChange={(event) => onChange(event.target.value)}
            spellCheck="false"
            value={markdown}
          />
        </label>
      ) : (
        <MarkdownPreview markdown={markdown} />
      )}
    </section>
  );
}
