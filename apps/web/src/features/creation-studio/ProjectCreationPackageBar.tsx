import { Check, PackageOpen } from "lucide-react";
import type { ProjectCreationPackageItem } from "@/features/creation-studio/projectCreationPackage";
import { cn } from "@/shared/lib/cn";

type ProjectCreationPackageBarProps = {
  activeId: string;
  items: ProjectCreationPackageItem[];
  onSelect: (id: string) => void;
  savedSlotKeys: ReadonlySet<string>;
};

export function ProjectCreationPackageBar({
  activeId,
  items,
  onSelect,
  savedSlotKeys,
}: ProjectCreationPackageBarProps) {
  return (
    <section
      aria-label="项目图片资产包"
      className="mx-auto mb-2 w-full max-w-[900px] shrink-0"
      data-testid="project-creation-package"
    >
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <span className="hidden shrink-0 items-center gap-1.5 px-1 text-xs font-semibold text-[var(--sh-ink-muted)] sm:flex">
          <PackageOpen aria-hidden="true" className="size-4" />
          本课资产
        </span>
        {items.map((item, index) => {
          const active = item.id === activeId;
          const saved = savedSlotKeys.has(item.slotKey);
          return (
            <button
              aria-pressed={active}
              className={cn(
                "flex min-w-[152px] flex-1 items-center gap-2 rounded-[var(--sh-radius-sm)] border px-3 py-2 text-left transition-[border-color,background-color,box-shadow] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)]",
                active
                  ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)] shadow-[var(--sh-shadow-card)]"
                  : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] hover:border-[var(--sh-line-strong)]",
              )}
              key={item.id}
              onClick={() => onSelect(item.id)}
              type="button"
            >
              <span
                className={cn(
                  "grid size-6 shrink-0 place-items-center rounded-full text-[11px] font-semibold",
                  saved
                    ? "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]"
                    : active
                      ? "bg-[var(--sh-brand-500)] text-white"
                      : "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
                )}
              >
                {saved ? <Check aria-hidden="true" className="size-3.5" /> : index + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[11px] font-medium text-[var(--sh-ink-muted)]">
                  {item.type}
                </span>
                <span className="block truncate text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {item.title}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
