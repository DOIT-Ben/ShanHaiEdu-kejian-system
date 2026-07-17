import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/lib/cn";

export function Checkbox({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      className={cn(
        "flex size-4.5 shrink-0 items-center justify-center rounded-[4px] border border-line bg-surface",
        "transition-colors duration-[var(--sh-motion-button)]",
        "hover:border-brand-500 focus-visible:outline-2 focus-visible:outline-brand focus-visible:outline-offset-2",
        "data-[state=checked]:border-brand-500 data-[state=checked]:bg-brand-500 data-[state=checked]:text-white",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator>
        <Check className="size-3.5" aria-hidden />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  );
}
