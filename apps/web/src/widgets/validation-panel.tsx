import { CheckCircle2, CircleAlert, Info, TriangleAlert } from "lucide-react";
import type { ValidationResult } from "@/shared/api/types";
import { cn } from "@/shared/lib/cn";
import { EmptyState } from "@/shared/ui";

const SEVERITY_META = {
  error: { icon: CircleAlert, className: "text-danger", label: "错误" },
  warning: { icon: TriangleAlert, className: "text-warning", label: "警告" },
  info: { icon: Info, className: "text-ink-muted", label: "提示" },
} as const;

/** 校验结果列表（检查器「校验」页签）。 */
export function ValidationPanel({
  results,
  onAction,
}: {
  results: ValidationResult[];
  onAction?: (result: ValidationResult) => void;
}) {
  if (results.length === 0) {
    return <EmptyState title="暂无校验结果" description="生成完成后，系统校验结果会显示在这里。" className="py-8" />;
  }
  const sorted = [...results].sort((a, b) => {
    const order = { error: 0, warning: 1, info: 2 } as const;
    if (a.passed !== b.passed) return a.passed ? 1 : -1;
    return order[(a.severity ?? "info") as keyof typeof order] - order[(b.severity ?? "info") as keyof typeof order];
  });
  return (
    <ul className="space-y-2">
      {sorted.map((result) => {
        const meta = SEVERITY_META[(result.severity ?? "info") as keyof typeof SEVERITY_META];
        const Icon = result.passed ? CheckCircle2 : meta.icon;
        return (
          <li
            key={result.rule_id}
            className={cn(
              "flex items-start gap-2.5 rounded-control border px-3 py-2.5",
              result.passed ? "border-line bg-surface-1" : "border-line bg-surface-2",
            )}
          >
            <Icon className={cn("mt-0.5 size-4 shrink-0", result.passed ? "text-success" : meta.className)} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm text-ink-1">{result.message}</p>
              {!result.passed && result.action && onAction ? (
                <button
                  type="button"
                  className="mt-1 text-xs font-medium text-brand hover:underline"
                  onClick={() => onAction(result)}
                >
                  {result.action}
                </button>
              ) : !result.passed && result.action ? (
                <p className="mt-1 text-xs text-ink-muted">建议：{result.action}</p>
              ) : null}
            </div>
            {!result.passed ? <span className={cn("text-xs", meta.className)}>{meta.label}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}
