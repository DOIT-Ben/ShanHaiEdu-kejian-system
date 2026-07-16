import type { ReactNode } from "react";
import { CheckCircle2, CloudUpload, AlertCircle } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export type SaveState = "idle" | "saving" | "saved" | "error";

/**
 * 自动保存状态指示：自动保存中 / 已保存 / 保存失败。
 */
export function SaveStatusIndicator({
  state,
  errorHint,
  className,
}: {
  state: SaveState;
  errorHint?: ReactNode;
  className?: string;
}) {
  if (state === "idle") return null;
  return (
    <span
      role="status"
      aria-live="polite"
      className={cn("inline-flex items-center gap-1.5 text-xs", className)}
    >
      {state === "saving" ? (
        <>
          <CloudUpload className="size-3.5 animate-pulse text-ink-muted" aria-hidden />
          <span className="text-ink-muted">自动保存中…</span>
        </>
      ) : state === "saved" ? (
        <>
          <CheckCircle2 className="size-3.5 text-success" aria-hidden />
          <span className="text-ink-2">已保存</span>
        </>
      ) : (
        <>
          <AlertCircle className="size-3.5 text-danger" aria-hidden />
          <span className="text-danger">{errorHint ?? "保存失败，请重试"}</span>
        </>
      )}
    </span>
  );
}
