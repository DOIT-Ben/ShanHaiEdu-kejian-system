import type { HTMLAttributes, ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/shared/lib/cn";
import type { StatusTone } from "@/shared/lib/status";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium leading-5",
  {
    variants: {
      tone: {
        neutral: "bg-surface-2 text-ink-2 border border-line",
        brand: "bg-brand-selected text-brand",
        running: "bg-running-surface text-running",
        success: "bg-success-surface text-success",
        warning: "bg-warning-surface text-warning",
        danger: "bg-danger-surface text-danger",
      } satisfies Record<StatusTone, string>,
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  icon?: ReactNode;
}

export function Badge({ className, tone, icon, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ tone }), className)} {...props}>
      {icon}
      {children}
    </span>
  );
}
