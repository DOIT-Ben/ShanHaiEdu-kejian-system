import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

export function PromptReviewDialog({
  description,
  onOpenChange,
  onRegenerate,
  onSave,
  open,
}: {
  description: string;
  onOpenChange: (open: boolean) => void;
  onRegenerate?: (description: string) => void;
  onSave: (description: string) => void;
  open: boolean;
}) {
  const [draft, setDraft] = useState(description);
  useEffect(() => {
    if (open) setDraft(description);
  }, [description, open]);
  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,720px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)]">
          <div className="flex items-center justify-between">
            <Dialog.Title className="text-xl font-bold text-[var(--sh-ink-strong)]">
              完整创作要求
            </Dialog.Title>
            <Dialog.Close asChild>
              <IconButton label="关闭">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-1 text-sm text-[var(--sh-ink-muted)]">
            你可以修改想要的内容，基本安全要求会自动保留。
          </Dialog.Description>
          <label className="mt-5 block">
            <span className="text-sm font-semibold">你想要的作品</span>
            <textarea
              className="mt-2 min-h-48 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] p-4 text-sm leading-6"
              onChange={(event) => setDraft(event.target.value)}
              value={draft}
            />
          </label>
          <div className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4">
            <p className="text-sm font-semibold">自动遵守</p>
            <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
              不出现不需要的文字、Logo 或水印；内容适合小学生观看；作品会按当前比例输出。
            </p>
          </div>
          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Dialog.Close asChild>
              <Button
                onClick={() => onSave(draft)}
                variant={onRegenerate ? "secondary" : "primary"}
              >
                保存创作要求
              </Button>
            </Dialog.Close>
            {onRegenerate ? (
              <Dialog.Close asChild>
                <Button disabled={draft.trim().length === 0} onClick={() => onRegenerate(draft)}>
                  保存并重新创作
                </Button>
              </Dialog.Close>
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
