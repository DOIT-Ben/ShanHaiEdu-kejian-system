import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-panel border border-dashed border-line bg-surface-2 px-6 py-12 text-center",
        className,
      )}
    >
      <div className="text-ink-muted">{icon ?? <Inbox className="size-8" aria-hidden />}</div>
      <p className="text-sm font-medium text-ink-1">{title}</p>
      {description ? <p className="max-w-sm text-sm text-ink-2">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
