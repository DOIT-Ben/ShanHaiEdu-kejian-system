import { AlertTriangle } from "lucide-react";

export function StaleContentNotice({ reason }: { reason?: string | null }) {
  return (
    <div className="mt-3 flex items-start gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] px-3 py-2 text-sm">
      <AlertTriangle
        aria-hidden="true"
        className="mt-0.5 size-4 shrink-0 text-[var(--sh-warning)]"
      />
      <div>
        <p className="font-semibold text-[var(--sh-ink-strong)]">前面的内容已经更新</p>
        <p className="mt-0.5 text-[var(--sh-ink-muted)]">
          {reason ?? "请检查当前内容并重新确认，旧版本会继续保留。"}
        </p>
      </div>
    </div>
  );
}
