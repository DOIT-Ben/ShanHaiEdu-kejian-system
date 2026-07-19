import * as Tooltip from "@radix-ui/react-tooltip";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/shared/lib/cn";

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
};

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ className, label, ...props }, ref) => (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          aria-label={label}
          className={cn(
            "inline-grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-md)] text-[var(--sh-ink-muted)] transition-[background-color,color,transform] duration-[var(--sh-duration-fast)] hover:-translate-y-px hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-brand-700)] disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-5",
            className,
          )}
          ref={ref}
          type="button"
          {...props}
        />
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          className="z-50 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-inverse)] px-2.5 py-1.5 text-xs text-white shadow-[var(--sh-shadow-floating)]"
          sideOffset={6}
        >
          {label}
          <Tooltip.Arrow className="fill-[var(--sh-surface-inverse)]" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  ),
);

IconButton.displayName = "IconButton";
