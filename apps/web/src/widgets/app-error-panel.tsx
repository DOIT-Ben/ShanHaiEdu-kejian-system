import { AppError } from "@/shared/api";
import { Button, ErrorRecoveryPanel } from "@/shared/ui";

const ACTION_HINT: Record<string, string> = {
  relogin: "请重新登录后继续。",
  retry: "可以直接重试。",
  reload: "请刷新后重试。",
  resolve_conflict: "请处理版本冲突后再保存。",
  authorize_budget: "请先完成预算授权。",
  complete_upstream: "请先完成上游步骤。",
  confirm_fallback: "需要确认切换备用服务。",
  resolve_validation: "请先处理未通过的校验项。",
  confirm_warnings: "请确认校验警告后继续。",
  resolve_blockers: "请先完成未就绪的交付项。",
};

/** AppError → 统一错误恢复面板（原因 + 费用说明 + Trace ID + 下一步）。 */
export function AppErrorPanel({
  error,
  title,
  onRetry,
  retryLabel = "重试",
  extraActions,
  className,
}: {
  error: unknown;
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
  extraActions?: React.ReactNode;
  className?: string;
}) {
  const appError = error instanceof AppError ? error : null;
  const message = appError?.message ?? (error instanceof Error ? error.message : "发生了未知错误。");
  const hint = appError?.action ? ACTION_HINT[appError.action] : undefined;
  return (
    <ErrorRecoveryPanel
      title={title ?? "操作未成功"}
      message={
        <>
          {message}
          {hint ? <span className="mt-0.5 block text-ink-muted">{hint}</span> : null}
        </>
      }
      traceId={appError?.traceId}
      className={className}
      actions={
        <>
          {onRetry ? (
            <Button size="sm" variant="secondary" onClick={onRetry}>
              {retryLabel}
            </Button>
          ) : null}
          {extraActions}
        </>
      }
    />
  );
}
