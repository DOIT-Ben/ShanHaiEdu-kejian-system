import { Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-live="polite" className="inline-flex items-center gap-2 text-ink">
      <Loader2 className={cn("size-4 animate-spin text-running", className)} aria-hidden />
      {label ? <span className="text-sm">{label}</span> : <span className="sr-only">加载中</span>}
    </span>
  );
}

/** 整页加载态（路由守卫 / 页面入口重定向用）。 */
export function FullScreenLoading({ label = "正在加载…" }: { label?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-1 items-center justify-center">
      <Spinner className="size-6" label={label} />
    </div>
  );
}
