import type { ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export function PageHeader({
  title,
  description,
  actions,
  breadcrumb,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  breadcrumb?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        {breadcrumb ? <div className="mb-1 text-sm text-ink-muted">{breadcrumb}</div> : null}
        <h1 className="truncate text-2xl font-semibold text-ink-strong">{title}</h1>
        {description ? <p className="mt-1 text-sm text-ink">{description}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
