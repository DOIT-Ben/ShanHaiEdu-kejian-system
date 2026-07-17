import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;

export function SelectTrigger({
  className,
  children,
  invalid,
  ...props
}: ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger> & { invalid?: boolean }) {
  return (
    <SelectPrimitive.Trigger
      aria-invalid={invalid || undefined}
      className={cn(
        "flex h-9 w-full items-center justify-between gap-2 rounded-control border border-line bg-surface px-3 text-sm text-ink-strong",
        "transition-colors duration-[var(--sh-motion-button)]",
        "hover:border-ink-muted/50 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20",
        "disabled:cursor-not-allowed disabled:bg-surface-soft disabled:text-ink-faint",
        "data-[placeholder]:text-ink-muted",
        invalid && "border-danger",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon asChild>
        <ChevronDown className="size-4 text-ink-muted" aria-hidden />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

export function SelectContent({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof SelectPrimitive.Content>) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Content
        position="popper"
        sideOffset={4}
        className={cn(
          "z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-y-auto rounded-overlay border border-line bg-surface p-1 shadow-lg",
          className,
        )}
        {...props}
      >
        <SelectPrimitive.Viewport>{children}</SelectPrimitive.Viewport>
      </SelectPrimitive.Content>
    </SelectPrimitive.Portal>
  );
}

export function SelectItem({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof SelectPrimitive.Item> & { children: ReactNode }) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "flex cursor-pointer items-center justify-between gap-2 rounded-control px-2.5 py-2 text-sm text-ink-strong outline-none",
        "data-[highlighted]:bg-brand-50 data-[highlighted]:text-brand-600",
        "data-[disabled]:pointer-events-none data-[disabled]:text-ink-faint",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator>
        <Check className="size-4" aria-hidden />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}
