import * as Dialog from "@radix-ui/react-dialog";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Ban,
  Check,
  Clock3,
  FolderOpen,
  ImagePlus,
  LoaderCircle,
  Play,
  RotateCcw,
  X,
} from "lucide-react";
import { useState } from "react";
import type { CreationQueueStatus } from "@/features/creation-studio/creationQueue";
import type { ProjectCreationPackageItem } from "@/features/creation-studio/projectCreationPackage";
import { cn } from "@/shared/lib/cn";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

type ProjectAssetDrawerProps = {
  activeId: string;
  items: ProjectCreationPackageItem[];
  lessonTitle: string;
  onCancel: (id: string) => void;
  onImport: (id: string) => void;
  onGenerateAll?: () => void;
  onOpenChange?: (open: boolean) => void;
  onRetry: (id: string) => void;
  projectTitle: string;
  savedSlotKeys: ReadonlySet<string>;
  taskStatuses: Record<string, CreationQueueStatus>;
};

function statusLabel(status: CreationQueueStatus, saved: boolean) {
  if (saved) return "已完成";
  if (status === "running") return "正在生成";
  if (status === "queued") return "排队中";
  if (status === "ready") return "等待采用";
  if (status === "cancelled") return "已取消";
  if (status === "failed") return "生成失败";
  return "可导入";
}

export function ProjectAssetDrawer({
  activeId,
  items,
  lessonTitle,
  onCancel,
  onImport,
  onGenerateAll,
  onOpenChange,
  onRetry,
  projectTitle,
  savedSlotKeys,
  taskStatuses,
}: ProjectAssetDrawerProps) {
  const [open, setOpen] = useState(false);
  const reduceMotion = useReducedMotion();
  const completed = items.filter((item) => savedSlotKeys.has(item.slotKey)).length;
  const pending = items.length - completed;
  const changeOpen = (nextOpen: boolean) => {
    setOpen(nextOpen);
    onOpenChange?.(nextOpen);
  };

  return (
    <Dialog.Root modal={false} onOpenChange={changeOpen} open={open}>
      <Dialog.Trigger asChild>
        <Button
          aria-label="打开项目资产"
          className="absolute right-3 top-3 z-20 shadow-[var(--sh-shadow-floating)]"
          size="sm"
          variant="secondary"
        >
          <FolderOpen aria-hidden="true" />
          <span className="hidden xl:inline">任务与资产</span>
          <span className="text-xs text-[var(--sh-ink-muted)]">
            {completed}/{items.length}
          </span>
        </Button>
      </Dialog.Trigger>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Content asChild forceMount>
              <motion.aside
                animate={{ opacity: 1, x: 0 }}
                aria-describedby="project-assets-description"
                className="fixed bottom-4 right-4 top-[calc(var(--sh-topbar-height)+60px)] z-50 flex w-[min(380px,calc(100vw-24px))] flex-col overflow-hidden rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-modal)] outline-none"
                exit={reduceMotion ? undefined : { opacity: 0, x: 20 }}
                initial={reduceMotion ? false : { opacity: 0, x: 24 }}
                transition={{ duration: reduceMotion ? 0 : 0.26, ease: [0.2, 0, 0, 1] }}
              >
                <div className="flex items-start justify-between gap-3 border-b border-[var(--sh-line-subtle)] px-4 py-3">
                  <div className="min-w-0">
                    <Dialog.Title className="font-semibold text-[var(--sh-ink-strong)]">
                      任务队列与项目资产
                    </Dialog.Title>
                    <Dialog.Description
                      className="mt-0.5 truncate text-xs text-[var(--sh-ink-muted)]"
                      id="project-assets-description"
                    >
                      {projectTitle} · {lessonTitle} · {String(completed)}/{String(items.length)}{" "}
                      已完成
                    </Dialog.Description>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {onGenerateAll && pending > 0 ? (
                      <Button onClick={onGenerateAll} size="sm">
                        <Play aria-hidden="true" />
                        全部加入队列
                      </Button>
                    ) : null}
                    <Dialog.Close asChild>
                      <IconButton className="size-9" label="关闭项目资产">
                        <X aria-hidden="true" />
                      </IconButton>
                    </Dialog.Close>
                  </div>
                </div>
                <div className="min-h-0 flex-1 overflow-y-auto p-3">
                  <div className="grid gap-2">
                    {items.map((item) => {
                      const active = item.id === activeId;
                      const saved = savedSlotKeys.has(item.slotKey);
                      const status = taskStatuses[item.id] ?? "idle";
                      const busy = status === "queued" || status === "running";
                      return (
                        <article
                          className={cn(
                            "flex w-full items-start gap-3 rounded-[var(--sh-radius-sm)] border p-3 text-left transition-[background-color,border-color,box-shadow,transform] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)]",
                            active
                              ? "border-[var(--sh-brand-400)] bg-[var(--sh-brand-50)] shadow-[var(--sh-shadow-card)]"
                              : "border-[var(--sh-line-subtle)] hover:border-[var(--sh-line-strong)] hover:bg-[var(--sh-surface-soft)]",
                          )}
                          key={item.id}
                        >
                          <span
                            className={cn(
                              "mt-0.5 grid size-8 shrink-0 place-items-center rounded-[var(--sh-radius-sm)]",
                              saved
                                ? "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]"
                                : "bg-[var(--sh-surface-soft)] text-[var(--sh-brand-700)]",
                            )}
                          >
                            {saved ? (
                              <Check aria-hidden="true" className="size-4" />
                            ) : (
                              <ImagePlus aria-hidden="true" className="size-4" />
                            )}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-xs font-medium text-[var(--sh-ink-muted)]">
                              {item.scope === "shot" ? "分镜资产" : "通用资产"} · {item.type} ·{" "}
                              {item.ratio}
                            </span>
                            <span className="mt-0.5 block font-semibold text-[var(--sh-ink-strong)]">
                              {item.title}
                            </span>
                            <span className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-[var(--sh-brand-700)]">
                              {status === "running" ? (
                                <LoaderCircle
                                  aria-hidden="true"
                                  className="size-3.5 animate-spin motion-reduce:animate-none"
                                />
                              ) : status === "queued" ? (
                                <Clock3 aria-hidden="true" className="size-3.5" />
                              ) : null}
                              {statusLabel(status, saved)}
                            </span>
                            <span className="mt-1 block max-h-10 overflow-hidden text-xs leading-5 text-[var(--sh-ink-muted)]">
                              {item.prompt}
                            </span>
                            {item.referenceNames?.length ? (
                              <span className="mt-1 block truncate text-xs text-[var(--sh-ink-muted)]">
                                参考：{item.referenceNames.join("、")}
                              </span>
                            ) : null}
                            <span className="mt-2 flex flex-wrap gap-1.5">
                              <Button
                                aria-label={`导入${item.type}：${item.title}`}
                                disabled={busy}
                                onClick={() => {
                                  onImport(item.id);
                                }}
                                size="sm"
                                variant={active ? "primary" : "secondary"}
                              >
                                <ImagePlus aria-hidden="true" />
                                导入
                              </Button>
                              {busy ? (
                                <Button
                                  aria-label={`取消${item.type}：${item.title}`}
                                  onClick={() => onCancel(item.id)}
                                  size="sm"
                                  variant="quiet"
                                >
                                  <Ban aria-hidden="true" />
                                  取消
                                </Button>
                              ) : status === "cancelled" || status === "failed" ? (
                                <Button
                                  aria-label={`重试${item.type}：${item.title}`}
                                  onClick={() => onRetry(item.id)}
                                  size="sm"
                                  variant="quiet"
                                >
                                  <RotateCcw aria-hidden="true" />
                                  重试
                                </Button>
                              ) : null}
                            </span>
                          </span>
                        </article>
                      );
                    })}
                  </div>
                </div>
              </motion.aside>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}
