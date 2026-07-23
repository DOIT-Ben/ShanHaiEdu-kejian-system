import * as Dialog from "@radix-ui/react-dialog";
import { RefreshCw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

export function ImageEditDialog({
  description,
  onApply,
  onOpenChange,
  open,
}: {
  description: string;
  onApply: (description: string) => void;
  onOpenChange: (open: boolean) => void;
  open: boolean;
}) {
  const [request, setRequest] = useState(description);

  useEffect(() => {
    if (open) setRequest(description);
  }, [description, open]);

  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,620px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-floating)] sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-lg font-semibold text-[var(--sh-ink-strong)]">
                编辑这张图片
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm leading-6 text-[var(--sh-ink-muted)]">
                描述要保留和修改的部分，当前图片会作为修改基础。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton label="关闭图片编辑">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>

          <label className="mt-5 block">
            <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">修改要求</span>
            <textarea
              aria-label="图片修改要求"
              className="mt-2 min-h-36 w-full resize-y rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] p-3 text-sm leading-6 outline-none focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)]"
              onChange={(event) => setRequest(event.target.value)}
              placeholder="例如：保留人物和桌面，把果汁瓶之间的距离拉开，减少背景装饰。"
              value={request}
            />
          </label>

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="quiet">取消</Button>
            </Dialog.Close>
            <Button
              disabled={!request.trim()}
              onClick={() => {
                onApply(request.trim());
                onOpenChange(false);
              }}
            >
              <RefreshCw aria-hidden="true" />
              生成修改版
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
