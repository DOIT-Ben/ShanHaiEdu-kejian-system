import { Clock3 } from "lucide-react";
import { useState } from "react";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import type { CreationSettings, StudioConfig, StudioType } from "@/features/creation-studio/model";

export function CreationSetupPanel({
  config,
  settings,
  type,
}: {
  config: StudioConfig;
  settings: CreationSettings;
  type: StudioType;
}) {
  const [selectedInspiration, setSelectedInspiration] = useState(0);
  const Icon = config.icon;
  const itemLabel = type === "image" ? "张" : type === "video" ? "段" : "套";
  const visualWidth = type === "image" ? "w-[clamp(180px,28vw,240px)]" : "w-full max-w-[560px]";
  const workspaceWidth = type === "image" ? "max-w-[720px]" : "max-w-[1040px]";

  return (
    <section
      aria-label="作品展示区"
      className={`mx-auto flex w-full ${workspaceWidth} flex-col justify-start`}
      data-testid="creation-output-region"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2">
          <span className="grid size-8 place-items-center rounded-full bg-[var(--sh-brand-100)] text-[var(--sh-brand-700)]">
            <Clock3 aria-hidden="true" className="size-4" />
          </span>
          <div>
            <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">等待开始创作</p>
            <p className="text-xs text-[var(--sh-ink-muted)]">
              在下方描述想法，作品会依次出现在这里
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--sh-ink-muted)]">
          <span className="rounded-full bg-[var(--sh-surface-elevated)] px-3 py-1.5 shadow-[var(--sh-shadow-card)]">
            0 个作品
          </span>
          <span className="rounded-full bg-[var(--sh-surface-elevated)] px-3 py-1.5 shadow-[var(--sh-shadow-card)]">
            可以开始创作
          </span>
        </div>
      </div>

      <div
        className="rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] p-2.5 shadow-[var(--sh-shadow-card)] sm:p-3"
        data-testid="creation-preview-panel"
      >
        <div className="flex items-center justify-between gap-3 px-1 pb-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="grid size-8 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
              <Icon aria-hidden="true" className="size-4" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                {config.entryTitle}
              </p>
              <p className="truncate text-xs text-[var(--sh-ink-muted)]">
                灵感预览，不会保存为你的作品
              </p>
            </div>
          </div>
          <span className="shrink-0 rounded-full bg-[var(--sh-surface-elevated)] px-2.5 py-1 text-xs text-[var(--sh-ink-muted)]">
            {settings.ratio} · {settings.candidateCount} {itemLabel}
          </span>
        </div>

        <div className={`relative mx-auto ${visualWidth}`} data-testid="creation-main-visual">
          <div className="overflow-hidden rounded-[var(--sh-radius-md)] border-[5px] border-[var(--sh-surface-elevated)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)]">
            <CreativeResultVisual
              ratio={settings.ratio}
              type={type}
              variant={selectedInspiration}
            />
          </div>
          <span className="absolute bottom-3 left-3 inline-flex items-center rounded-full bg-[var(--sh-surface-elevated)]/92 px-3 py-1.5 text-xs font-medium text-[var(--sh-brand-700)] shadow-[var(--sh-shadow-card)] backdrop-blur-sm">
            灵感预览
          </span>
        </div>

        <div aria-label="画面灵感" className="mx-auto mt-3 flex max-w-[360px] justify-center gap-2">
          {[0, 1, 2].map((variant) => (
            <button
              aria-label={`画面灵感 ${String(variant + 1)}`}
              aria-pressed={selectedInspiration === variant}
              className={`w-[76px] overflow-hidden rounded-[var(--sh-radius-sm)] border-2 bg-[var(--sh-surface-elevated)] p-1 transition-[border-color,transform] hover:-translate-y-0.5 ${selectedInspiration === variant ? "border-[var(--sh-brand-500)]" : "border-[var(--sh-surface-elevated)]"}`}
              key={variant}
              onClick={() => setSelectedInspiration(variant)}
              type="button"
            >
              <CreativeResultVisual ratio="4:3" type={type} variant={variant} />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
