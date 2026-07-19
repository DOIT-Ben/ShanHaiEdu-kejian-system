import { ChevronRight, FileText, ImagePlus, Settings2 } from "lucide-react";
import type { CreationSettings, StudioType } from "@/features/creation-studio/model";
import { cn } from "@/shared/lib/cn";
import { Select } from "@/shared/ui/Select";

const modelOptions: Record<StudioType, Array<{ label: string; value: string }>> = {
  image: [
    { label: "课堂插画 · 均衡", value: "balanced" },
    { label: "细节增强", value: "detail" },
    { label: "快速草图", value: "fast" },
  ],
  video: [
    { label: "课堂视频 · 均衡", value: "balanced" },
    { label: "动作稳定", value: "detail" },
    { label: "快速预览", value: "fast" },
  ],
  presentation: [
    { label: "课堂课件 · 均衡", value: "balanced" },
    { label: "图文增强", value: "detail" },
    { label: "快速排版", value: "fast" },
  ],
};

const controlClass =
  "inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] px-2.5 text-xs text-[var(--sh-ink-muted)] transition-colors hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)] focus-within:border-[var(--sh-brand-500)]";

function ParameterSelect({
  ariaLabel,
  className,
  disabled,
  label,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  className?: string;
  disabled: boolean;
  label: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  return (
    <Select
      ariaLabel={ariaLabel}
      className={cn(
        "shrink-0 border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] sm:w-auto sm:max-w-48",
        className,
      )}
      disabled={disabled}
      leadingLabel={label}
      onValueChange={onChange}
      options={options}
      size="sm"
      value={value}
    />
  );
}

export function CreationParameterBar({
  advancedOpen,
  disabled,
  onAdvancedOpenChange,
  onPromptReview,
  onSettingsChange,
  settings,
  type,
}: {
  advancedOpen: boolean;
  disabled: boolean;
  onAdvancedOpenChange: (open: boolean) => void;
  onPromptReview: () => void;
  onSettingsChange: (settings: Partial<CreationSettings>) => void;
  settings: CreationSettings;
  type: StudioType;
}) {
  const itemLabel = type === "image" ? "张" : type === "video" ? "段" : "套";
  return (
    <div className="relative min-w-0">
      <div
        aria-label="创作参数"
        className="flex min-w-0 items-center gap-1.5 overflow-x-auto pb-0.5 pr-10 [scrollbar-width:none] xl:pr-0 [&::-webkit-scrollbar]:hidden"
        data-testid="creation-parameter-bar"
      >
        <ParameterSelect
          ariaLabel="创作模型"
          className="w-[120px]"
          disabled={disabled}
          label="模型"
          onChange={(model) => onSettingsChange({ model })}
          options={modelOptions[type]}
          value={settings.model}
        />
        <ParameterSelect
          ariaLabel="比例"
          className="w-[84px]"
          disabled={disabled}
          label="比例"
          onChange={(ratio) => onSettingsChange({ ratio })}
          options={[
            { label: "16:9", value: "16:9" },
            { label: "1:1", value: "1:1" },
            { label: "4:3", value: "4:3" },
          ]}
          value={settings.ratio}
        />
        <ParameterSelect
          ariaLabel="画面风格"
          className="w-[108px]"
          disabled={disabled}
          label="风格"
          onChange={(style) => onSettingsChange({ style })}
          options={[
            { label: "纸艺微缩", value: "paper" },
            { label: "清透插画", value: "illustration" },
            { label: "柔和黏土", value: "clay" },
          ]}
          value={settings.style}
        />
        <ParameterSelect
          ariaLabel="一次生成数量"
          className="w-[92px]"
          disabled={disabled}
          label="数量"
          onChange={(candidateCount) => onSettingsChange({ candidateCount })}
          options={[
            { label: `2 ${itemLabel}`, value: "2" },
            { label: `3 ${itemLabel}`, value: "3" },
            { label: `4 ${itemLabel}`, value: "4" },
          ]}
          value={settings.candidateCount}
        />
        {type === "video" ? (
          <ParameterSelect
            ariaLabel="持续时间"
            className="w-[88px]"
            disabled={disabled}
            label="时长"
            onChange={(duration) => onSettingsChange({ duration })}
            options={[
              { label: "10 秒", value: "10" },
              { label: "15 秒", value: "15" },
            ]}
            value={settings.duration}
          />
        ) : null}
        <label className={`${controlClass} cursor-pointer`}>
          <ImagePlus aria-hidden="true" className="size-3.5" />
          <span className="max-w-28 truncate font-semibold text-[var(--sh-ink-strong)]">
            {settings.referenceName || "参考图"}
          </span>
          <input
            accept="image/*"
            aria-label="添加参考图"
            className="sr-only"
            disabled={disabled}
            onChange={(event) =>
              onSettingsChange({ referenceName: event.target.files?.[0]?.name ?? "" })
            }
            type="file"
          />
        </label>
        <button
          aria-expanded={advancedOpen}
          className={`${controlClass} font-semibold text-[var(--sh-ink-strong)] disabled:cursor-wait disabled:opacity-50`}
          disabled={disabled}
          onClick={() => onAdvancedOpenChange(!advancedOpen)}
          type="button"
        >
          <Settings2 aria-hidden="true" className="size-3.5" />
          画面细节
        </button>
        <button
          aria-label="查看完整创作要求"
          className={`${controlClass} font-semibold text-[var(--sh-ink-strong)] disabled:cursor-wait disabled:opacity-50`}
          disabled={disabled}
          onClick={onPromptReview}
          type="button"
        >
          <FileText aria-hidden="true" className="size-3.5" />
          完整要求
        </button>
      </div>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 right-0 flex w-11 items-center justify-end bg-gradient-to-l from-[var(--sh-surface-elevated)] via-[var(--sh-surface-elevated)]/88 to-transparent pr-1 text-[var(--sh-brand-600)] xl:hidden"
        data-testid="creation-parameter-overflow-hint"
      >
        <ChevronRight className="size-4" />
      </span>
    </div>
  );
}
