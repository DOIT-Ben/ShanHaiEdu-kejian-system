import * as PopoverPrimitive from "@radix-ui/react-popover";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/lib/cn";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;
export const PopoverClose = PopoverPrimitive.Close;

export function PopoverContent({
  className,
  sideOffset = 6,
  ...props
}: ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>) {
  return (
    <PopoverPrimitive.Portal>
      <PopoverPrimitive.Content
        sideOffset={sideOffset}
        className={cn(
          "z-50 w-80 rounded-overlay border border-line bg-surface p-4 shadow-lg outline-none",
          className,
        )}
        {...props}
      />
    </PopoverPrimitive.Portal>
  );
}
