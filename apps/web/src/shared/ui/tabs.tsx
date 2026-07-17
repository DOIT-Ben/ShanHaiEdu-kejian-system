import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentPropsWithoutRef } from "react";
import { cn } from "@/shared/lib/cn";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "inline-flex items-center gap-1 rounded-control bg-surface-soft p-1",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded-[6px] px-3 py-1.5 text-sm text-ink outline-none",
        "transition-colors duration-[var(--sh-motion-tab)]",
        "hover:text-ink-strong focus-visible:outline-2 focus-visible:outline-brand",
        "data-[state=active]:bg-surface data-[state=active]:font-medium data-[state=active]:text-ink-strong data-[state=active]:shadow-sm",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}

export function TabsContent({
  className,
  ...props
}: ComponentPropsWithoutRef<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content
      className={cn("outline-none focus-visible:outline-none", className)}
      {...props}
    />
  );
}
