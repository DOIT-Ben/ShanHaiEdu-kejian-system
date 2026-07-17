import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/shared/lib/cn";

export const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-1.5 rounded-control font-medium",
    "transition-colors duration-[var(--sh-motion-button)] transition-token",
    "focus-visible:outline-2 focus-visible:outline-brand focus-visible:outline-offset-2",
    "disabled:pointer-events-none disabled:opacity-50",
    "whitespace-nowrap select-none",
  ].join(" "),
  {
    variants: {
      variant: {
        primary: "bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-600",
        secondary: "bg-brand-50 text-brand-600 hover:bg-[#e0e9ff] active:bg-[#d5e1ff]",
        outline: "border border-line bg-surface text-ink-strong hover:bg-canvas",
        ghost: "text-ink hover:bg-canvas hover:text-ink-strong",
        destructive: "bg-danger text-white hover:bg-[#c2353b]",
        "destructive-outline": "border border-danger/40 bg-surface text-danger hover:bg-danger-50",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-4 text-sm",
        lg: "h-10 px-5 text-sm",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  loadingText?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, loading, loadingText, children, disabled, type, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        type={asChild ? undefined : (type ?? "button")}
        className={cn(buttonVariants({ variant, size }), className)}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...props}
      >
        {loading ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden />
            <span>{loadingText ?? children}</span>
          </>
        ) : (
          children
        )}
      </Comp>
    );
  },
);
Button.displayName = "Button";
