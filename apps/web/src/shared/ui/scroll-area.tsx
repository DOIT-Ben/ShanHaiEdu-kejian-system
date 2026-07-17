import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/lib/cn";

export function ScrollArea({
  className,
  children,
  ...props
}: ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>) {
  return (
    <ScrollAreaPrimitive.Root className={cn("overflow-hidden", className)} {...props}>
      <ScrollAreaPrimitive.Viewport className="size-full rounded-[inherit]">
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollAreaPrimitive.Scrollbar
        orientation="vertical"
        className="flex w-2 touch-none select-none p-0.5"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-line" />
      </ScrollAreaPrimitive.Scrollbar>
      <ScrollAreaPrimitive.Scrollbar
        orientation="horizontal"
        className="flex h-2 touch-none select-none p-0.5"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-line" />
      </ScrollAreaPrimitive.Scrollbar>
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  );
}
