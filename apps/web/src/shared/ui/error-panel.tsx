import type { ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/shared/lib/cn";

/**
 * 阻断性错误面板：持续显示错误原因、Trace ID 与下一步解决动作。
 * 文案规则：发生了什么 + 是否扣费 + 下一步怎么做。
 */
export function ErrorRecoveryPanel({
  title,
  message,
  traceId,
  costNote,
  actions,
  className,
}: {
  title: string;
  message?: ReactNode;
  traceId?: string | null;
  costNote?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn("rounded-panel border border-danger/30 bg-danger-surface px-5 py-4", className)}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-ink-1">{title}</p>
          {message ? <div className="mt-1 text-sm text-ink-2">{message}</div> : null}
          {costNote ? <p className="mt-1 text-xs text-ink-2">{costNote}</p> : null}
          {traceId ? (
            <p className="mt-2 font-mono text-xs text-ink-muted">Trace ID：{traceId}</p>
          ) : null}
          {actions ? <div className="mt-3 flex flex-wrap items-center gap-2">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}
