import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export function Panel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-panel border border-line bg-surface", className)}
      {...props}
    />
  );
}

export function PanelHeader({
  title,
  description,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-divider px-5 py-4", className)}>
      <div className="min-w-0">
        <h3 className="truncate text-base font-semibold text-ink-strong">{title}</h3>
        {description ? <p className="mt-0.5 text-sm text-ink">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function PanelBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-5", className)} {...props} />;
}
