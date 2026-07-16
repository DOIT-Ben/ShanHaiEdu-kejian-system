import { GitMerge } from "lucide-react";
import { Button, Dialog, DialogContent } from "@/shared/ui";

/**
 * 版本冲突处理对话框（409 VERSION_CONFLICT）：
 * 保留我的修改（基于服务器版本重新提交）/ 使用服务器版本 / 另存为副本。
 */
export function ConflictDialog({
  open,
  onOpenChange,
  serverRowVersion,
  onKeepMine,
  onUseServer,
  onSaveAsCopy,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  serverRowVersion?: number | null;
  onKeepMine: () => void;
  onUseServer: () => void;
  onSaveAsCopy?: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title="内容已在其他位置被修改"
        description={
          serverRowVersion
            ? `服务器上已有更新的版本（第 ${serverRowVersion} 次修改）。请选择如何处理你的改动。`
            : "服务器上已有更新的版本。请选择如何处理你的改动。"
        }
      >
        <div className="space-y-2">
          <button
            type="button"
            onClick={onKeepMine}
            className="flex w-full items-start gap-3 rounded-control border border-line px-4 py-3 text-left transition-colors hover:border-brand hover:bg-brand-selected"
          >
            <GitMerge className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
            <span>
              <span className="block text-sm font-medium text-ink-1">保留我的修改</span>
              <span className="block text-xs text-ink-2">基于服务器最新版本重新提交你的改动（推荐）。</span>
            </span>
          </button>
          <button
            type="button"
            onClick={onUseServer}
            className="flex w-full items-start gap-3 rounded-control border border-line px-4 py-3 text-left transition-colors hover:border-brand hover:bg-brand-selected"
          >
            <span className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              <span className="block text-sm font-medium text-ink-1">放弃我的修改</span>
              <span className="block text-xs text-ink-2">加载服务器版本，丢弃本地未保存的改动。</span>
            </span>
          </button>
          {onSaveAsCopy ? (
            <button
              type="button"
              onClick={onSaveAsCopy}
              className="flex w-full items-start gap-3 rounded-control border border-line px-4 py-3 text-left transition-colors hover:border-brand hover:bg-brand-selected"
            >
              <span className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>
                <span className="block text-sm font-medium text-ink-1">另存为新版本</span>
                <span className="block text-xs text-ink-2">把我的改动保存为一个新的版本，稍后再合并。</span>
              </span>
            </button>
          ) : null}
        </div>
        <div className="mt-2 text-right">
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            稍后处理
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
