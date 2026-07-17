import { useEffect, useState } from "react";
import { ChevronDown, Lock, PencilLine } from "lucide-react";
import { usePromptPreview, useSavePrompt } from "@/features/node-runs";
import { AppError } from "@/shared/api";
import { cn } from "@/shared/lib/cn";
import { Button, Skeleton, Textarea, toast } from "@/shared/ui";

/**
 * 完整生成指令（03 §6）：提示词永远可见可编辑，绝不隐藏。
 * 可编辑业务提示词 + 只读系统约束层 + 上下文来源说明。
 */
export function PromptSection({
  nodeRunId,
  defaultOpen = false,
  onRevision,
  className,
}: {
  nodeRunId: string;
  defaultOpen?: boolean;
  onRevision?: (promptRevisionId: string) => void;
  className?: string;
}) {
  const { data, isPending } = usePromptPreview(nodeRunId);
  const save = useSavePrompt(nodeRunId);
  const [open, setOpen] = useState(defaultOpen);
  const [draft, setDraft] = useState<string | null>(null);

  useEffect(() => {
    setDraft(null); // 节点切换时丢弃本地草稿
  }, [nodeRunId]);

  const preview = data?.preview;
  const value = draft ?? preview?.editable_prompt ?? "";
  const dirty = draft !== null && draft !== preview?.editable_prompt;

  const persist = () => {
    if (!data || !dirty || !draft?.trim()) return;
    save.mutate(
      { etag: data.etag ?? "", editablePrompt: draft },
      {
        onSuccess: (revision) => {
          setDraft(null);
          onRevision?.(revision.prompt_revision_id);
          toast({ tone: "success", title: "生成指令已保存", description: "本次生成将使用修改后的指令。" });
        },
        onError: (error) => {
          if (error instanceof AppError && error.isEditConflict) {
            toast({ tone: "warning", title: "指令已在其他位置修改", description: "已刷新为最新内容，请基于最新版本调整。" });
            setDraft(null);
          } else {
            toast({ tone: "danger", title: "保存失败", description: error.message });
          }
        },
      },
    );
  };

  return (
    <section className={cn("rounded-lg border border-line-subtle bg-surface", className)}>
      <button
        type="button"
        className="flex w-full items-center gap-2 px-4 py-3 text-left"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <PencilLine className="size-4 shrink-0 text-brand-600" aria-hidden />
        <span className="flex-1 text-sm font-medium text-ink-strong">查看和修改完整生成指令</span>
        {dirty ? <span className="text-xs text-warning">有未保存修改</span> : null}
        <ChevronDown
          className={cn("size-4 shrink-0 text-ink-faint transition-transform duration-150", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="space-y-4 border-t border-line-subtle px-4 py-4">
          {isPending || !preview ? (
            <Skeleton className="h-32 rounded-md" />
          ) : (
            <>
              {preview.context_summary.length > 0 ? (
                <div className="rounded-md bg-surface-soft p-3">
                  <p className="text-xs font-medium text-ink-muted">这次生成会参考：</p>
                  <ul className="mt-1.5 space-y-1">
                    {preview.context_summary.map((item, index) => (
                      <li key={index} className="text-xs leading-relaxed text-ink">
                        · {item.title}
                        {item.detail ? <span className="text-ink-muted">（{item.detail}）</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <div>
                <label htmlFor={`prompt-${nodeRunId}`} className="text-xs font-medium text-ink-muted">
                  生成指令（可编辑）
                </label>
                <Textarea
                  id={`prompt-${nodeRunId}`}
                  value={value}
                  rows={8}
                  className="mt-1.5 font-mono text-[13px] leading-relaxed"
                  onChange={(event) => setDraft(event.target.value)}
                />
                <div className="mt-2 flex items-center gap-2">
                  <Button size="sm" onClick={persist} disabled={!dirty} loading={save.isPending} loadingText="保存中…">
                    保存指令
                  </Button>
                  {dirty ? (
                    <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>
                      放弃修改
                    </Button>
                  ) : null}
                </div>
              </div>
              {preview.locked_layers.length > 0 ? (
                <div>
                  <p className="flex items-center gap-1.5 text-xs font-medium text-ink-muted">
                    <Lock className="size-3.5" aria-hidden />
                    系统约束（只读，保证格式与安全）
                  </p>
                  <ul className="mt-1.5 space-y-1.5">
                    {preview.locked_layers.map((layer, index) => (
                      <li key={index} className="rounded-md border border-line-subtle bg-canvas p-2.5 text-xs leading-relaxed text-ink-muted">
                        <span className="font-medium text-ink">{layer.title}</span>
                        {layer.summary ? <span className="mt-0.5 block">{layer.summary}</span> : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
