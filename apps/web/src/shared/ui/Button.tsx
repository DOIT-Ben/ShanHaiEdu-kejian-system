import { Slot, Slottable } from "@radix-ui/react-slot";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export type ButtonInteractionState = "idle" | "loading" | "success" | "error";

export const buttonVariants = cva(
  "relative inline-flex min-h-10 shrink-0 items-center justify-center gap-1.5 rounded-[var(--sh-radius-control)] px-3.5 text-sm font-medium transition-[color,background-color,border-color,box-shadow,transform] duration-[var(--sh-duration-fast)] motion-reduce:transform-none motion-reduce:transition-none disabled:pointer-events-none [&_svg]:size-4",
  {
    variants: {
      variant: {
        primary:
          "border border-[var(--sh-action-border)] bg-[var(--sh-action-primary)] font-semibold text-[var(--sh-action-foreground)] shadow-[var(--sh-shadow-action)] hover:-translate-y-px hover:bg-[var(--sh-action-hover)] hover:shadow-[var(--sh-shadow-action-hover)] active:translate-y-px active:bg-[var(--sh-action-active)] active:shadow-[var(--sh-shadow-action-active)] disabled:border-[var(--sh-line-subtle)] disabled:bg-[var(--sh-surface-soft)] disabled:text-[var(--sh-ink-faint)] disabled:shadow-none disabled:opacity-100",
        secondary:
          "border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] text-[var(--sh-ink-default)] shadow-[var(--sh-shadow-card)] hover:-translate-y-px hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)] hover:text-[var(--sh-brand-700)] active:translate-y-px active:shadow-none disabled:text-[var(--sh-ink-disabled)] disabled:shadow-none disabled:opacity-70",
        quiet:
          "bg-transparent text-[var(--sh-brand-600)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-brand-700)] active:bg-[var(--sh-brand-50)] disabled:text-[var(--sh-ink-disabled)] disabled:opacity-70",
        danger:
          "border border-[var(--sh-danger-strong)] bg-[var(--sh-danger)] font-semibold text-[var(--sh-on-accent)] shadow-[var(--sh-shadow-card)] hover:-translate-y-px hover:bg-[var(--sh-danger-strong)] hover:shadow-[var(--sh-shadow-hover)] active:translate-y-px active:shadow-none disabled:border-[var(--sh-line-subtle)] disabled:bg-[var(--sh-surface-soft)] disabled:text-[var(--sh-ink-faint)] disabled:opacity-100",
      },
      size: {
        sm: "sh-control-compact min-h-9 px-3 text-[13px]",
        md: "min-h-10 px-3.5",
        lg: "min-h-11 px-4 text-sm",
      },
      state: {
        idle: "",
        loading: "cursor-wait",
        success:
          "border-[var(--sh-success)] bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)] shadow-none hover:translate-y-0 hover:bg-[var(--sh-success-soft)] hover:shadow-none",
        error:
          "border-[var(--sh-danger)] bg-[var(--sh-danger-soft)] text-[var(--sh-danger-strong)] shadow-none hover:translate-y-0 hover:bg-[var(--sh-danger-soft)] hover:shadow-none",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
      state: "idle",
    },
  },
);

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  Omit<VariantProps<typeof buttonVariants>, "state"> & {
    asChild?: boolean;
    error?: boolean;
    errorText?: string;
    loading?: boolean;
    loadingText?: string;
    success?: boolean;
    successText?: string;
  };

function resolveState({
  error,
  loading,
  success,
}: Pick<ButtonProps, "error" | "loading" | "success">) {
  if (loading) return "loading" as const;
  if (error) return "error" as const;
  if (success) return "success" as const;
  return "idle" as const;
}

function stateLabel(
  state: ButtonInteractionState,
  loadingText: string,
  successText: string,
  errorText: string,
) {
  if (state === "loading") return loadingText;
  if (state === "success") return successText;
  if (state === "error") return errorText;
  return "";
}

function StateIcon({ state }: { state: ButtonInteractionState }) {
  if (state === "loading") {
    return <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" />;
  }
  if (state === "success") return <CircleCheck aria-hidden="true" />;
  if (state === "error") return <CircleAlert aria-hidden="true" />;
  return null;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      asChild = false,
      children,
      className,
      disabled = false,
      error = false,
      errorText = "操作失败",
      loading = false,
      loadingText = "正在处理",
      onClick,
      size,
      success = false,
      successText = "操作成功",
      type = "button",
      variant,
      ...props
    },
    ref,
  ) => {
    const state = resolveState({ error, loading, success });
    const liveText = stateLabel(state, loadingText, successText, errorText);
    const effectiveDisabled = disabled || state === "loading";
    const Component = asChild ? Slot : "button";
    const accessibleLabel =
      state === "idle"
        ? props["aria-label"]
        : props["aria-label"]
          ? `${props["aria-label"]}：${liveText}`
          : liveText;
    const handleClick = (event: MouseEvent<HTMLElement>) => {
      if (effectiveDisabled) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      onClick?.(event as MouseEvent<HTMLButtonElement>);
    };

    return (
      <>
        <Component
          {...props}
          aria-busy={state === "loading" ? true : undefined}
          aria-disabled={asChild && effectiveDisabled ? true : undefined}
          aria-label={accessibleLabel}
          className={cn(buttonVariants({ size, state, variant }), className)}
          data-slot="button"
          data-state={state}
          disabled={asChild ? undefined : effectiveDisabled}
          onClick={effectiveDisabled || onClick ? handleClick : undefined}
          ref={ref}
          tabIndex={asChild && effectiveDisabled ? -1 : props.tabIndex}
          type={asChild ? undefined : type}
        >
          {state !== "idle" ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute inset-0 grid place-items-center"
              data-slot="button-state"
            >
              <StateIcon state={state} />
            </span>
          ) : null}
          <Slottable child={children}>
            {(content: ReactNode) => (
              <span
                className={cn(
                  "inline-flex items-center justify-center gap-1.5",
                  state !== "idle" && "invisible",
                )}
                data-slot="button-content"
              >
                {content}
              </span>
            )}
          </Slottable>
        </Component>
        {liveText ? (
          <span
            aria-live={state === "error" ? "assertive" : "polite"}
            className="sr-only"
            role={state === "error" ? "alert" : "status"}
          >
            {liveText}
          </span>
        ) : null}
      </>
    );
  },
);

Button.displayName = "Button";
