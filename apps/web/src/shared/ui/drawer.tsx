import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export const Drawer = DialogPrimitive.Root;
export const DrawerTrigger = DialogPrimitive.Trigger;
export const DrawerClose = DialogPrimitive.Close;

/**
 * 右侧抽屉（1024–1279 宽度下检查器的承载形态，以及各类详情面板）。
 */
export function DrawerContent({
  className,
  children,
  title,
  description,
  width = "w-[480px]",
  ...props
}: ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  title: ReactNode;
  description?: ReactNode;
  width?: string;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-surface-inverse/30" />
      <DialogPrimitive.Content
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex max-w-[92vw] flex-col border-l border-line bg-surface shadow-xl",
          "duration-[var(--sh-motion-overlay)]",
          width,
          className,
        )}
        {...props}
      >
        <div className="flex items-start justify-between gap-4 border-b border-divider px-5 py-4">
          <div className="min-w-0">
            <DialogPrimitive.Title className="truncate text-base font-semibold text-ink-strong">
              {title}
            </DialogPrimitive.Title>
            {description ? (
              <DialogPrimitive.Description className="mt-0.5 text-sm text-ink">
                {description}
              </DialogPrimitive.Description>
            ) : null}
          </div>
          <DialogPrimitive.Close
            aria-label="关闭"
            className="rounded-control p-1 text-ink-muted transition-colors hover:bg-canvas hover:text-ink-strong focus-visible:outline-2 focus-visible:outline-brand"
          >
            <X className="size-4" aria-hidden />
          </DialogPrimitive.Close>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
