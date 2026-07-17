import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/shared/lib/cn";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

const iconButtonVariants = cva(
  [
    "inline-flex items-center justify-center rounded-control",
    "transition-colors duration-[var(--sh-motion-button)] transition-token",
    "focus-visible:outline-2 focus-visible:outline-brand focus-visible:outline-offset-2",
    "disabled:pointer-events-none disabled:opacity-50",
  ].join(" "),
  {
    variants: {
      variant: {
        ghost: "text-ink hover:bg-canvas hover:text-ink-strong",
        outline: "border border-line bg-surface text-ink hover:bg-canvas hover:text-ink-strong",
        danger: "text-danger hover:bg-danger-50",
      },
      size: {
        sm: "size-7",
        md: "size-8",
        lg: "size-9",
      },
    },
    defaultVariants: { variant: "ghost", size: "md" },
  },
);

export interface IconButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof iconButtonVariants> {
  /** 图标按钮必须有可读名称（用于 aria-label 与 Tooltip）。 */
  label: string;
  withTooltip?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, variant, size, label, withTooltip = true, children, ...props }, ref) => {
    const button = (
      <button
        ref={ref}
        type="button"
        aria-label={label}
        className={cn(iconButtonVariants({ variant, size }), className)}
        {...props}
      >
        {children}
      </button>
    );
    if (!withTooltip) return button;
    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
    );
  },
);
IconButton.displayName = "IconButton";
