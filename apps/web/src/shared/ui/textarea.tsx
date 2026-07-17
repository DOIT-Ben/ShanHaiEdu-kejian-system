import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  /** 等宽字体（提示词编辑等场景）。 */
  mono?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, invalid, mono, ...props }, ref) => (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        "w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink-strong",
        "placeholder:text-ink-muted",
        "transition-colors duration-[var(--sh-motion-button)]",
        "hover:border-ink-muted/50 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20",
        "disabled:cursor-not-allowed disabled:bg-surface-soft disabled:text-ink-faint",
        mono && "font-mono text-[13px] leading-relaxed",
        invalid && "border-danger focus:border-danger focus:ring-danger/20",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";
