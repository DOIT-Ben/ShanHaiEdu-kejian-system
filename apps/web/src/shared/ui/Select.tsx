import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { forwardRef, type FocusEventHandler, type ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export type SelectOption = {
  disabled?: boolean;
  label: string;
  value: string;
};

type SelectProps = {
  ariaLabel: string;
  className?: string;
  disabled?: boolean;
  leadingLabel?: ReactNode;
  name?: string;
  onBlur?: FocusEventHandler<HTMLButtonElement>;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  size?: "sm" | "md" | "lg";
  value?: string;
};

const sizeClasses = {
  sm: "sh-control-compact h-9 px-2.5 text-xs",
  md: "h-10 px-3 text-sm",
  lg: "h-11 px-3.5 text-sm",
};

export const Select = forwardRef<HTMLButtonElement, SelectProps>(function Select(
  {
    ariaLabel,
    className,
    disabled = false,
    leadingLabel,
    name,
    onBlur,
    onValueChange,
    options,
    placeholder = "请选择",
    size = "md",
    value,
  },
  ref,
) {
  if (options.some((option) => option.value.length === 0)) {
    throw new Error("Select 选项值不能为空，请使用 placeholder 表示未选择状态。");
  }

  return (
    <SelectPrimitive.Root
      disabled={disabled}
      name={name}
      onValueChange={onValueChange}
      value={value}
    >
      <SelectPrimitive.Trigger
        aria-label={ariaLabel}
        className={cn(
          "group inline-flex min-w-0 items-center justify-between gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] text-left text-[var(--sh-ink-default)] shadow-[var(--sh-shadow-card)] outline-none transition-[border-color,background-color,box-shadow] duration-[var(--sh-duration-fast)] hover:border-[var(--sh-brand-300)] hover:bg-[var(--sh-brand-50)] focus-visible:border-[var(--sh-brand-500)] focus-visible:shadow-[var(--sh-shadow-focus)] data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50",
          sizeClasses[size],
          className,
        )}
        data-slot="select-trigger"
        onBlur={onBlur}
        ref={ref}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          {leadingLabel ? (
            <span className="shrink-0 text-[var(--sh-ink-muted)]">{leadingLabel}</span>
          ) : null}
          <span className="min-w-0 truncate font-medium text-[var(--sh-ink-strong)]">
            <SelectPrimitive.Value placeholder={placeholder} />
          </span>
        </span>
        <SelectPrimitive.Icon asChild>
          <ChevronDown
            aria-hidden="true"
            className="size-3.5 shrink-0 text-[var(--sh-ink-faint)] transition-transform duration-[var(--sh-duration-fast)] group-data-[state=open]:rotate-180"
          />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          align="start"
          className="sh-select-content z-[70] max-h-[min(var(--radix-select-content-available-height),280px)] min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-1 shadow-[var(--sh-shadow-floating)]"
          position="popper"
          sideOffset={5}
        >
          <SelectPrimitive.Viewport>
            {options.map((option) => (
              <SelectPrimitive.Item
                className="sh-control-compact relative flex min-h-9 cursor-default select-none items-center rounded-md py-2 pl-3 pr-9 text-sm text-[var(--sh-ink-default)] outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-45 data-[highlighted]:bg-[var(--sh-brand-50)] data-[highlighted]:text-[var(--sh-brand-900)] data-[state=checked]:font-semibold"
                disabled={option.disabled}
                key={option.value}
                value={option.value}
              >
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator className="absolute right-3 grid size-4 place-items-center text-[var(--sh-brand-700)]">
                  <Check aria-hidden="true" className="size-3.5" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
});

Select.displayName = "Select";
