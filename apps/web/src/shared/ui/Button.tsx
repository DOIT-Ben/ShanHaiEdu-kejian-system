import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export const buttonVariants = cva(
  "inline-flex min-h-10 shrink-0 items-center justify-center gap-1.5 rounded-[var(--sh-radius-sm)] px-3.5 text-sm font-medium transition-[color,background-color,border-color,box-shadow,transform] duration-[var(--sh-duration-fast)] disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-4",
  {
    variants: {
      variant: {
        primary:
          "bg-[var(--sh-brand-700)] bg-[image:var(--sh-action-gradient)] text-white shadow-[var(--sh-shadow-card)] hover:-translate-y-px hover:bg-[image:var(--sh-action-gradient-hover)] hover:shadow-[var(--sh-shadow-hover)] active:translate-y-px active:shadow-[var(--sh-shadow-card)]",
        secondary:
          "border border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)] text-[var(--sh-brand-600)] hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-surface-soft)] hover:shadow-[var(--sh-shadow-card)]",
        quiet:
          "bg-transparent text-[var(--sh-brand-600)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-brand-700)]",
        danger:
          "bg-[var(--sh-danger)] text-white shadow-[var(--sh-shadow-card)] hover:bg-[var(--sh-danger-strong)] hover:shadow-[var(--sh-shadow-hover)] active:translate-y-px",
      },
      size: {
        sm: "sh-control-compact min-h-9 px-3 text-[13px]",
        md: "min-h-10 px-3.5",
        lg: "min-h-11 px-4 text-sm",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ asChild = false, className, size, variant, type = "button", ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return (
      <Component
        className={cn(buttonVariants({ size, variant }), className)}
        data-slot="button"
        ref={ref}
        type={asChild ? undefined : type}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
