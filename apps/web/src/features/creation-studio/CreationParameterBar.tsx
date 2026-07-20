import { FileText, Settings2 } from "lucide-react";
import type { ReactNode } from "react";
import type { CreationSettings, StudioType } from "@/features/creation-studio/model";
import { Button } from "@/shared/ui/Button";
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

function ParameterSelect({
  ariaLabel,
  disabled,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  disabled: boolean;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  return (
    <Select
      ariaLabel={ariaLabel}
      className="w-full min-w-0 border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]"
      disabled={disabled}
      onValueChange={onChange}
      options={options}
      size="sm"
      value={value}
    />
  );
}

function ParameterField({
  ariaLabel,
  disabled,
  label,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  disabled: boolean;
  label: string;
  onChange: (value: string) => void;
  options: Array<{ label: string; value: string }>;
  value: string;
}) {
  return (
    <label className="grid min-w-0 gap-1">
      <span className="text-[11px] font-medium text-[var(--sh-ink-muted)]">{label}</span>
      <ParameterSelect
        ariaLabel={ariaLabel}
        disabled={disabled}
        onChange={onChange}
        options={options}
        value={value}
      />
    </label>
  );
}

export function CreationParameterBar({
  advancedOpen,
  disabled,
  onAdvancedOpenChange,
  onPromptReview,
  referenceAction,
  onSettingsChange,
  settings,
  type,
}: {
  advancedOpen: boolean;
  disabled: boolean;
  onAdvancedOpenChange: (open: boolean) => void;
  onPromptReview: () => void;
  referenceAction?: ReactNode;
  onSettingsChange: (settings: Partial<CreationSettings>) => void;
  settings: CreationSettings;
  type: StudioType;
}) {
  const itemLabel = type === "image" ? "张" : type === "video" ? "段" : "套";

  return (
    <div
      aria-label="创作设置"
      className="sh-creation-settings-panel rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-3 shadow-[var(--sh-shadow-floating)]"
      data-testid="creation-parameter-bar"
      role="group"
    >
      <div className="grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4 xl:grid-cols-5">
        <ParameterField
          ariaLabel="创作模型"
          disabled={disabled}
          label="模型"
          onChange={(model) => onSettingsChange({ model })}
          options={modelOptions[type]}
          value={settings.model}
        />
        <ParameterField
          ariaLabel="比例"
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
        <ParameterField
          ariaLabel="画面风格"
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
        <ParameterField
          ariaLabel="一次生成数量"
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
          <ParameterField
            ariaLabel="持续时间"
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
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-[var(--sh-line-subtle)] pt-2.5">
        {referenceAction ? <div className="sm:hidden">{referenceAction}</div> : null}
        <Button
          aria-controls="creation-advanced-panel"
          aria-expanded={advancedOpen}
          disabled={disabled}
          onClick={() => onAdvancedOpenChange(!advancedOpen)}
          size="sm"
          variant="quiet"
        >
          <Settings2 aria-hidden="true" />
          画面细节
        </Button>
        <Button disabled={disabled} onClick={onPromptReview} size="sm" variant="quiet">
          <FileText aria-hidden="true" />
          完整要求
        </Button>
      </div>
    </div>
  );
}
