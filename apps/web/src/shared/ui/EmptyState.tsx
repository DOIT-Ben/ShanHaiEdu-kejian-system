import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
};

export function EmptyState({ action, description, icon: Icon, title }: EmptyStateProps) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-5 grid size-14 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
        <Icon aria-hidden="true" className="size-6" />
      </div>
      <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]">{title}</h2>
      <p className="mt-2 max-w-md text-sm text-[var(--sh-ink-muted)]">{description}</p>
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}
