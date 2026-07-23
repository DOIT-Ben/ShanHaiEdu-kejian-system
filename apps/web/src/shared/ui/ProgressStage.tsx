import { LoaderCircle } from "lucide-react";

export function ProgressStage({ label, detail }: { label: string; detail?: string }) {
  return (
    <div
      aria-live="polite"
      className="flex items-center gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-brand-100)] bg-[var(--sh-brand-50)] px-4 py-3"
    >
      <LoaderCircle
        aria-hidden="true"
        className="size-5 animate-spin text-[var(--sh-brand-600)] motion-reduce:animate-none"
      />
      <div>
        <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">{label}</p>
        {detail ? <p className="text-xs text-[var(--sh-ink-muted)]">{detail}</p> : null}
      </div>
    </div>
  );
}
