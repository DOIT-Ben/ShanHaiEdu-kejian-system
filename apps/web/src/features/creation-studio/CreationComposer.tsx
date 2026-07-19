import { ChevronDown, ChevronUp, LoaderCircle, Plus, Settings2, X } from "lucide-react";
import { type ReactNode, useState } from "react";
import { CreationParameterBar } from "@/features/creation-studio/CreationParameterBar";
import type {
  CreationSettings,
  CreationStage,
  StudioConfig,
  StudioType,
} from "@/features/creation-studio/model";
import {
  appendTeacherSuggestion,
  teacherPromptSuggestions,
} from "@/features/creation-studio/teacherPromptSuggestions";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

function generationLabels(type: StudioType, stage: CreationStage, primaryLabel: string) {
  if (stage === "draft") return { compact: "开始创作", full: primaryLabel };
  if (stage === "running") return { compact: "创作中", full: "正在创作" };
  return {
    compact: "重新创作",
    full: type === "image" ? "按新要求再画一组" : "按新要求再做一组",
  };
}

export function CreationComposer({
  advancedOpen,
  advancedPanel,
  config,
  description,
  descriptionLabel,
  hasUnappliedChanges,
  onAdvancedOpenChange,
  onDescriptionChange,
  onGenerate,
  onPromptReview,
  onSettingsChange,
  settings,
  stage,
  type,
}: {
  advancedOpen: boolean;
  advancedPanel: ReactNode;
  config: StudioConfig;
  description: string;
  descriptionLabel: string;
  hasUnappliedChanges: boolean;
  onAdvancedOpenChange: (open: boolean) => void;
  onDescriptionChange: (description: string) => void;
  onGenerate: () => void;
  onPromptReview: () => void;
  onSettingsChange: (settings: Partial<CreationSettings>) => void;
  settings: CreationSettings;
  stage: CreationStage;
  type: StudioType;
}) {
  const [mobileDetailsOpen, setMobileDetailsOpen] = useState(false);
  const running = stage === "running";
  const inputLabel = stage === "draft" ? descriptionLabel : "创作要求";
  const labels = generationLabels(type, stage, config.primaryLabel);
  const status = running
    ? "本轮要求已经提交"
    : hasUnappliedChanges
      ? "有修改，重新创作后生效"
      : "本地草稿已保存";
  const toggleMobileDetails = () => {
    if (advancedOpen) onAdvancedOpenChange(false);
    setMobileDetailsOpen((value) => !value);
  };

  return (
    <section
      aria-label="创作输入区"
      className="relative z-30 shrink-0 bg-gradient-to-t from-[var(--sh-surface-canvas)] via-[var(--sh-surface-canvas)] to-transparent px-3 pb-[calc(12px+env(safe-area-inset-bottom))] pt-2"
      data-testid="creation-composer"
    >
      {advancedOpen ? (
        <div className="absolute bottom-[calc(100%-8px)] left-1/2 z-40 max-h-[min(52vh,460px)] w-[min(1040px,calc(100vw-24px))] -translate-x-1/2 overflow-y-auto rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-modal)]">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-[var(--sh-ink-strong)]">画面细节</p>
              <p className="text-xs text-[var(--sh-ink-muted)]">
                这些调整会和下面的创作要求一起用于下一次创作。
              </p>
            </div>
            <IconButton label="关闭画面细节" onClick={() => onAdvancedOpenChange(false)}>
              <X aria-hidden="true" />
            </IconButton>
          </div>
          {advancedPanel}
        </div>
      ) : null}

      <div
        className="mx-auto max-w-[1040px] rounded-[22px] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]/96 p-3 shadow-[var(--sh-shadow-modal)] backdrop-blur-xl"
        data-testid="creation-composer-panel"
      >
        <div className="sh-creation-status-line flex items-center justify-between gap-3 px-1 text-xs">
          <p className="truncate font-medium text-[var(--sh-brand-700)]">
            {stage === "draft" ? `先从这一步开始 · ${config.entryTitle}` : "继续调整这件作品"}
          </p>
          <p
            className={
              hasUnappliedChanges
                ? "shrink-0 text-[var(--sh-warning)]"
                : "shrink-0 text-[var(--sh-ink-muted)]"
            }
          >
            {status}
          </p>
        </div>

        <div className="mt-2 flex items-stretch gap-2">
          <label className="min-w-0 flex-1">
            <span className="sr-only">{inputLabel}</span>
            <textarea
              aria-label={inputLabel}
              className="sh-creation-prompt min-h-24 max-h-32 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)] px-3 py-2.5 text-sm leading-5 text-[var(--sh-ink-default)] outline-none transition-[border-color,box-shadow] placeholder:text-[var(--sh-ink-faint)] hover:border-[var(--sh-line-strong)] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)] disabled:cursor-wait disabled:opacity-65 sm:min-h-20"
              disabled={running}
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder="说说你希望画面呈现什么，也可以补充想调整的地方……"
              value={description}
            />
          </label>
          <Button
            aria-label={labels.full}
            className="h-10 min-h-10 w-[96px] shrink-0 self-end sm:w-[148px] sm:self-center"
            disabled={running || description.trim().length === 0}
            onClick={onGenerate}
            size="md"
          >
            {running ? (
              <LoaderCircle
                aria-hidden="true"
                className="hidden animate-spin motion-reduce:animate-none sm:block"
              />
            ) : null}
            <span className="sm:hidden">{labels.compact}</span>
            <span className="hidden sm:inline">{labels.full}</span>
          </Button>
          <IconButton
            aria-expanded={mobileDetailsOpen}
            className="sh-creation-short-settings hidden self-end"
            label={mobileDetailsOpen ? "收起创作参数" : "调整创作参数"}
            onClick={toggleMobileDetails}
          >
            <Settings2 aria-hidden="true" />
          </IconButton>
        </div>

        <button
          aria-expanded={mobileDetailsOpen}
          className="sh-creation-mobile-toggle mt-2 flex min-h-9 w-full items-center justify-between rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 text-xs font-semibold text-[var(--sh-brand-700)] sm:hidden"
          onClick={toggleMobileDetails}
          type="button"
        >
          {mobileDetailsOpen ? "收起创作参数" : "调整模型、比例和画面细节"}
          {mobileDetailsOpen ? (
            <ChevronUp aria-hidden="true" className="size-4" />
          ) : (
            <ChevronDown aria-hidden="true" className="size-4" />
          )}
        </button>
        <div
          className={`sh-creation-details ${mobileDetailsOpen ? "flex" : "hidden"} mt-2 min-w-0 flex-col gap-1.5 sm:flex sm:flex-row sm:items-center sm:gap-2`}
        >
          <div aria-label="课堂创作建议" className="flex shrink-0 gap-2 overflow-x-auto">
            {teacherPromptSuggestions[type].slice(0, 1).map((suggestion) => (
              <button
                className="inline-flex min-h-8 shrink-0 items-center gap-1 rounded-full border border-[var(--sh-brand-100)] bg-[var(--sh-brand-50)] px-2.5 text-xs font-medium text-[var(--sh-brand-700)] hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-surface-elevated)] disabled:cursor-wait disabled:opacity-50"
                disabled={running}
                key={suggestion.label}
                onClick={() =>
                  onDescriptionChange(appendTeacherSuggestion(description, suggestion))
                }
                type="button"
              >
                <Plus aria-hidden="true" className="size-3.5" />
                {suggestion.label}
              </button>
            ))}
          </div>
          <span
            aria-hidden="true"
            className="hidden h-5 w-px bg-[var(--sh-line-subtle)] sm:block"
          />
          <div className="min-w-0 flex-1">
            <CreationParameterBar
              advancedOpen={advancedOpen}
              disabled={running}
              onAdvancedOpenChange={(open) => {
                if (open) setMobileDetailsOpen(false);
                onAdvancedOpenChange(open);
              }}
              onPromptReview={onPromptReview}
              onSettingsChange={onSettingsChange}
              settings={settings}
              type={type}
            />
            <p className="mt-1 px-1 text-[11px] text-[var(--sh-ink-faint)] sm:hidden">
              左右滑动查看更多参数
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
