import * as Dialog from "@radix-ui/react-dialog";
import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { IconButton } from "@/shared/ui/IconButton";

export type SearchEntry = {
  detail: string;
  label: string;
  to: string;
};

type GlobalSearchDialogProps = {
  entries?: readonly SearchEntry[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function GlobalSearchDialog({ entries = [], onOpenChange, open }: GlobalSearchDialogProps) {
  const [query, setQuery] = useState("");
  const results = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return entries;
    return entries.filter((entry) =>
      `${entry.label} ${entry.detail}`.toLowerCase().includes(keyword),
    );
  }, [entries, query]);

  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]"
          data-testid="global-search-overlay"
        />
        <Dialog.Content className="fixed left-1/2 top-[12vh] z-50 w-[min(92vw,640px)] -translate-x-1/2 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-floating)]">
          <div className="flex items-center gap-3">
            <Search aria-hidden="true" className="size-5 shrink-0 text-[var(--sh-ink-faint)]" />
            <Dialog.Title className="sr-only">全局搜索</Dialog.Title>
            <Dialog.Description className="sr-only">
              搜索项目、课时、创作工具和任务
            </Dialog.Description>
            <input
              aria-label="搜索项目、课时和功能"
              autoFocus
              className="min-h-11 min-w-0 flex-1 bg-transparent outline-none placeholder:text-[var(--sh-ink-faint)]"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索项目、课时和功能"
              value={query}
            />
            <Dialog.Close asChild>
              <IconButton label="关闭搜索">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div className="mt-3 max-h-[56vh] overflow-y-auto border-t border-[var(--sh-line-subtle)] pt-3">
            {results.length > 0 ? (
              <ul className="space-y-1">
                {results.map((entry) => (
                  <li key={entry.to}>
                    <Link
                      className="flex min-h-12 items-center justify-between gap-4 rounded-[var(--sh-radius-sm)] px-3 py-2 hover:bg-[var(--sh-surface-soft)]"
                      onClick={() => onOpenChange(false)}
                      to={entry.to}
                    >
                      <span className="font-medium text-[var(--sh-ink-strong)]">{entry.label}</span>
                      <span className="shrink-0 text-xs text-[var(--sh-ink-muted)]">
                        {entry.detail}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-3 py-8 text-center text-sm text-[var(--sh-ink-muted)]">
                {entries.length > 0
                  ? "没有找到相关内容，请换个关键词。"
                  : "当前没有可搜索的项目或功能。"}
              </p>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
