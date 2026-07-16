import { Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role="status" aria-live="polite" className={cn("inline-flex items-center gap-2 text-ink-2", className)}>
      <Loader2 className="size-4 animate-spin text-running" aria-hidden />
      {label ? <span className="text-sm">{label}</span> : <span className="sr-only">加载中</span>}
    </span>
  );
}
