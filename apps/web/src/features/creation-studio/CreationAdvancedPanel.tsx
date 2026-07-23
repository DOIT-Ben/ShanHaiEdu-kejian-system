import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import { IconButton } from "@/shared/ui/IconButton";

export type CreationAdvancedSettings = {
  composition: string;
  negativePrompt: string;
  referenceStrength: number;
};

export function CreationAdvancedPanel({
  embedded = false,
  onChange,
  onClose,
  settings,
}: {
  embedded?: boolean;
  onChange: (settings: Partial<CreationAdvancedSettings>) => void;
  onClose?: () => void;
  settings: CreationAdvancedSettings;
}) {
  const firstFieldRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!embedded) return;
    const frame = window.requestAnimationFrame(() => {
      firstFieldRef.current?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [embedded]);

  return (
    <aside
      aria-label="画面细节调整"
      className={
        embedded ? "" : "border-l border-[var(--sh-line-default)] bg-[var(--sh-surface-base)] p-5"
      }
    >
      {!embedded ? (
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">画面细节</h2>
          <IconButton label="关闭画面细节" onClick={onClose}>
            <X aria-hidden="true" />
          </IconButton>
        </div>
      ) : null}
      <div
        className={
          embedded
            ? "grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_220px] md:items-start"
            : "mt-5 space-y-5"
        }
      >
        <label className="block">
          <span className="text-sm font-semibold">画面安排</span>
          <textarea
            className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)] p-3 text-sm leading-5 transition-[border-color,box-shadow] duration-[var(--sh-duration-fast)] hover:border-[var(--sh-line-strong)] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)]"
            onChange={(event) => onChange({ composition: event.target.value })}
            ref={firstFieldRef}
            value={settings.composition}
          />
        </label>
        <label className="block">
          <span className="text-sm font-semibold">画面里不要出现</span>
          <textarea
            className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)] p-3 text-sm leading-5 transition-[border-color,box-shadow] duration-[var(--sh-duration-fast)] hover:border-[var(--sh-line-strong)] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)]"
            onChange={(event) => onChange({ negativePrompt: event.target.value })}
            value={settings.negativePrompt}
          />
        </label>
        <label
          className={
            embedded
              ? "block rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-3"
              : "block"
          }
        >
          <span className="flex items-center justify-between gap-3 text-sm font-semibold">
            参考图相似程度
            <output className="font-normal text-[var(--sh-ink-muted)]">
              {settings.referenceStrength}%
            </output>
          </span>
          <input
            aria-label="参考图相似程度"
            className="mt-3 w-full accent-[var(--sh-brand-500)]"
            max="100"
            min="0"
            onChange={(event) => onChange({ referenceStrength: event.target.valueAsNumber })}
            type="range"
            value={settings.referenceStrength}
          />
        </label>
      </div>
    </aside>
  );
}
