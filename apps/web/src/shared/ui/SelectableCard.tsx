import { Check } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

type SelectableCardProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  children: ReactNode;
  selected: boolean;
  selectedLabel?: string;
};

export function SelectableCard({
  children,
  className,
  selected,
  selectedLabel = "已选中",
  type = "button",
  ...props
}: SelectableCardProps) {
  return (
    <button
      aria-pressed={selected}
      className={cn(
        "group relative min-w-0 rounded-[var(--sh-radius-md)] border bg-[var(--sh-surface-elevated)] text-left transition-[border-color,background-color,box-shadow,transform] duration-[var(--sh-duration-fast)] motion-reduce:transition-none",
        "hover:-translate-y-0.5 hover:border-[var(--sh-brand-300)] hover:shadow-[var(--sh-shadow-hover)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--sh-brand-500)] focus-visible:ring-offset-2",
        selected &&
          "border-[var(--sh-brand-600)] bg-[var(--sh-brand-50)] shadow-[var(--sh-shadow-card)] ring-1 ring-[var(--sh-brand-200)]",
        className,
      )}
      type={type}
      {...props}
    >
      {children}
      {selected ? (
        <span className="pointer-events-none absolute right-2 top-2 inline-flex items-center gap-1 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-700)] px-1.5 py-1 text-[10px] font-semibold text-white shadow-[var(--sh-shadow-card)]">
          <Check aria-hidden="true" className="size-3" />
          {selectedLabel}
        </span>
      ) : null}
    </button>
  );
}
