import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { cn } from "@/shared/lib/cn";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  hideClose,
  ...props
}: ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
  title: ReactNode;
  description?: ReactNode;
  hideClose?: boolean;
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-ink-1/30 backdrop-blur-[1px]" />
      <DialogPrimitive.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2",
          "rounded-overlay border border-line bg-surface-1 p-6 shadow-xl",
          "duration-[var(--sh-motion-overlay)]",
          className,
        )}
        {...props}
      >
        <DialogPrimitive.Title className="pr-8 text-lg font-semibold text-ink-1">
          {title}
        </DialogPrimitive.Title>
        {description ? (
          <DialogPrimitive.Description className="mt-1 text-sm text-ink-2">
            {description}
          </DialogPrimitive.Description>
        ) : null}
        <div className="mt-4">{children}</div>
        {!hideClose ? (
          <DialogPrimitive.Close
            aria-label="关闭"
            className="absolute right-4 top-4 rounded-control p-1 text-ink-muted transition-colors hover:bg-surface-hover hover:text-ink-1 focus-visible:outline-2 focus-visible:outline-brand"
          >
            <X className="size-4" aria-hidden />
          </DialogPrimitive.Close>
        ) : null}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogFooter({ className, ...props }: { className?: string; children: ReactNode }) {
  return <div className={cn("mt-6 flex justify-end gap-2", className)} {...props} />;
}
