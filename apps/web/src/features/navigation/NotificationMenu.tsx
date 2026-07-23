import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Bell, CheckCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

export type NotificationItem = {
  detail: string;
  title: string;
  to: string;
};

type NotificationMenuProps = {
  notifications?: readonly NotificationItem[];
};

export function NotificationMenu({ notifications = [] }: NotificationMenuProps) {
  const [unread, setUnread] = useState(notifications.length);

  return (
    <DropdownMenu.Root onOpenChange={(open) => open && setUnread(0)}>
      <DropdownMenu.Trigger asChild>
        <button
          aria-label={unread > 0 ? `通知，${String(unread)} 条未读` : "通知"}
          className="relative inline-grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"
          type="button"
        >
          <Bell aria-hidden="true" className="size-5" />
          {unread > 0 ? (
            <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-[var(--sh-danger)]" />
          ) : null}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          className="z-50 w-[min(92vw,380px)] rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-2 shadow-[var(--sh-shadow-floating)]"
          sideOffset={8}
        >
          <div className="flex items-center justify-between px-2 py-2">
            <DropdownMenu.Label className="font-semibold text-[var(--sh-ink-strong)]">
              通知
            </DropdownMenu.Label>
            {notifications.length > 0 ? (
              <span className="inline-flex items-center gap-1 text-xs text-[var(--sh-success)]">
                <CheckCheck aria-hidden="true" className="size-3.5" />
                已全部读过
              </span>
            ) : null}
          </div>
          <DropdownMenu.Separator className="my-1 h-px bg-[var(--sh-line-subtle)]" />
          {notifications.length > 0 ? (
            notifications.map((item) => (
              <DropdownMenu.Item asChild key={item.title}>
                <Link
                  className="block rounded-[var(--sh-radius-sm)] px-3 py-3 outline-none hover:bg-[var(--sh-surface-soft)] focus:bg-[var(--sh-surface-soft)]"
                  to={item.to}
                >
                  <span className="block text-sm font-semibold text-[var(--sh-ink-strong)]">
                    {item.title}
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-[var(--sh-ink-muted)]">
                    {item.detail}
                  </span>
                </Link>
              </DropdownMenu.Item>
            ))
          ) : (
            <p className="px-3 py-8 text-center text-sm text-[var(--sh-ink-muted)]">暂无新通知</p>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
