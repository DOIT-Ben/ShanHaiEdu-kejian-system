import { CheckCircle2, Info } from "lucide-react";

export function CreationSessionBoundaryNotice() {
  return (
    <div className="flex gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-4 py-3 text-sm text-[var(--sh-ink-muted)]">
      <Info aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-[var(--sh-brand-600)]" />
      <p>独立创作不依赖课程项目。当前暂时无法生成或恢复作品，请稍后再试。</p>
    </div>
  );
}

export function CreationResultUnavailableNotice() {
  return (
    <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-success)]/30 bg-[var(--sh-success-soft)] p-5">
      <div className="flex gap-3">
        <CheckCircle2
          aria-hidden="true"
          className="mt-0.5 size-5 shrink-0 text-[var(--sh-success)]"
        />
        <div>
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">作品生成任务已完成</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
            当前服务尚未提供生成结果读取，暂时不能在这里查看、选用或保存到项目。
          </p>
        </div>
      </div>
    </section>
  );
}
