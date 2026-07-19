import type { ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

type FocusPageHeaderProps = {
  eyebrow?: string;
  hideEyebrow?: boolean;
  title: string;
  description?: string;
  status?: ReactNode;
  supporting?: ReactNode;
  action?: ReactNode;
};

export function FocusPageHeader({
  action,
  description,
  eyebrow,
  hideEyebrow = false,
  status,
  supporting,
  title,
}: FocusPageHeaderProps) {
  return (
    <header
      className={cn(
        "grid min-w-0 gap-3",
        supporting && action
          ? "lg:grid-cols-[minmax(240px,1fr)_minmax(280px,0.85fr)_auto] lg:items-center"
          : supporting
            ? "md:grid-cols-[minmax(240px,1fr)_minmax(320px,1fr)] md:items-center"
            : action
              ? "sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start"
              : undefined,
      )}
      data-slot="page-header"
    >
      <div className="min-w-0 max-w-3xl">
        {eyebrow && !hideEyebrow ? (
          <p className="mb-1 text-xs font-semibold text-[var(--sh-brand-600)]">{eyebrow}</p>
        ) : eyebrow ? (
          <span className="sr-only">{eyebrow}</span>
        ) : null}
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <h1 className="break-words text-[22px] font-semibold leading-tight text-[var(--sh-ink-strong)] md:text-[24px]">
            {title}
          </h1>
          {status}
        </div>
        {description ? (
          <p className="mt-1 max-w-2xl text-xs leading-5 text-[var(--sh-ink-muted)] md:text-sm">
            {description}
          </p>
        ) : null}
      </div>
      {supporting ? (
        <div
          className="min-w-0"
          data-slot="page-header-supporting"
          data-testid="page-header-supporting"
        >
          {supporting}
        </div>
      ) : null}
      {action ? (
        <div
          className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-self-end"
          data-slot="page-header-action"
        >
          {action}
        </div>
      ) : null}
    </header>
  );
}
