import * as Tooltip from "@radix-ui/react-tooltip";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/shared/lib/cn";
import type { ButtonInteractionState } from "@/shared/ui/Button";

export const iconButtonVariants = cva(
  "relative inline-grid size-11 shrink-0 place-items-center rounded-[var(--sh-radius-control)] transition-[background-color,border-color,box-shadow,color,transform] duration-[var(--sh-duration-fast)] motion-reduce:transform-none motion-reduce:transition-none disabled:pointer-events-none [&_svg]:size-5",
  {
    variants: {
      variant: {
        default:
          "text-[var(--sh-ink-muted)] hover:-translate-y-px hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-brand-700)] active:translate-y-px disabled:text-[var(--sh-ink-disabled)] disabled:opacity-70",
        primary:
          "border border-[var(--sh-action-border)] bg-[var(--sh-action-primary)] text-[var(--sh-action-foreground)] shadow-[var(--sh-shadow-action)] hover:-translate-y-px hover:bg-[var(--sh-action-hover)] hover:text-[var(--sh-action-foreground)] hover:shadow-[var(--sh-shadow-action-hover)] active:translate-y-px active:bg-[var(--sh-action-active)] active:shadow-[var(--sh-shadow-action-active)] disabled:border-[var(--sh-line-subtle)] disabled:bg-[var(--sh-surface-soft)] disabled:text-[var(--sh-ink-faint)] disabled:shadow-none disabled:opacity-100",
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
      variant: "default",
      state: "idle",
    },
  },
);

type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> &
  Omit<VariantProps<typeof iconButtonVariants>, "state"> & {
    children?: ReactNode;
    error?: boolean;
    errorText?: string;
    label: string;
    loading?: boolean;
    loadingText?: string;
    success?: boolean;
    successText?: string;
  };

function resolveState({
  error,
  loading,
  success,
}: Pick<IconButtonProps, "error" | "loading" | "success">) {
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

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      className,
      disabled = false,
      error = false,
      errorText = "操作失败",
      label,
      loading = false,
      loadingText = "正在处理",
      onClick,
      success = false,
      successText = "操作成功",
      variant,
      children,
      ...props
    },
    ref,
  ) => {
    const state = resolveState({ error, loading, success });
    const liveText = stateLabel(state, loadingText, successText, errorText);
    const effectiveDisabled = disabled || state === "loading";
    const currentLabel = liveText ? `${label}：${liveText}` : label;

    return (
      <>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <button
              {...props}
              aria-busy={state === "loading" ? true : undefined}
              aria-label={currentLabel}
              className={cn(iconButtonVariants({ state, variant }), className)}
              data-slot="icon-button"
              data-state={state}
              disabled={effectiveDisabled}
              onClick={onClick}
              ref={ref}
              type="button"
            >
              {state !== "idle" ? (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-0 grid place-items-center"
                  data-slot="icon-button-state"
                >
                  <StateIcon state={state} />
                </span>
              ) : null}
              <span className={state !== "idle" ? "invisible" : undefined}>{children}</span>
            </button>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content
              className="z-50 rounded-[var(--sh-radius-control)] bg-[var(--sh-surface-inverse)] px-2.5 py-1.5 text-xs text-[var(--sh-on-accent)] shadow-[var(--sh-shadow-floating)]"
              sideOffset={6}
            >
              {currentLabel}
              <Tooltip.Arrow className="fill-[var(--sh-surface-inverse)]" />
            </Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
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

IconButton.displayName = "IconButton";
