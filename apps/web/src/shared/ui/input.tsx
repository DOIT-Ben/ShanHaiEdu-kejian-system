import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, invalid, "aria-invalid": ariaInvalid, ...props }, ref) => (
    <input
      ref={ref}
      aria-invalid={invalid || ariaInvalid || undefined}
      className={cn(
        "h-9 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink-strong",
        "placeholder:text-ink-muted",
        "transition-colors duration-[var(--sh-motion-button)]",
        "hover:border-ink-muted/50 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20",
        "disabled:cursor-not-allowed disabled:bg-surface-soft disabled:text-ink-faint",
        invalid && "border-danger focus:border-danger focus:ring-danger/20",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
