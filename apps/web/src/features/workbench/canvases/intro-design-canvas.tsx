import { useMemo, useState } from "react";
import { Anchor, CheckCircle2, Copy, Lock, PencilLine } from "lucide-react";
import { introDesignContentSchema, parseContent, type IntroOption } from "@/entities/content";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, Dialog, DialogContent, DialogFooter, FormField, Textarea } from "@/shared/ui";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

function anchorTone(status: string): "success" | "warning" | "danger" {
  return status === "confirmed" ? "success" : status === "failed" ? "danger" : "warning";
}

function OptionCard({
  option,
  selected,
  pending,
  onApprove,
  onRevise,
  onLockRedo,
  onDuplicate,
}: {
  option: IntroOption;
  selected: boolean;
  pending?: boolean;
  onApprove: () => void;
  onRevise: (instruction: string) => void;
  onLockRedo: () => void;
  onDuplicate: () => void;
}) {
  const [reviseOpen, setReviseOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const hasFailedAnchor = option.anchors.some((anchor) => anchor.status === "failed");

  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-card border bg-surface-1 p-4 transition-shadow",
        selected ? "border-brand ring-2 ring-brand/25" : "border-line hover:shadow-sm",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-ink-1">
          方案{option.option_no}｜{option.title}
        </h4>
        {selected ? <Badge tone="brand">已选定</Badge> : null}
      </div>
      <p className="mt-1.5 text-sm leading-6 text-ink-2">{option.summary}</p>
      {option.narrative ? <p className="mt-1 text-xs leading-5 text-ink-muted">{option.narrative}</p> : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
        {option.style_hint ? <span>风格：{option.style_hint}</span> : null}
        <span>时长约 {option.duration_seconds} 秒</span>
        {option.creative_locked ? (
          <span className="inline-flex items-center gap-0.5 text-warning">
            <Lock className="size-3" aria-hidden />
            创意已锁定
          </span>
        ) : null}
      </div>
      <div className="mt-3 space-y-1.5">
        {option.anchors.map((anchor) => (
          <div key={anchor.anchor_id} className="flex items-start gap-1.5">
            <Anchor className="mt-0.5 size-3.5 shrink-0 text-ink-muted" aria-hidden />
            <p className="min-w-0 flex-1 text-xs leading-5 text-ink-2">
              {anchor.description}
              <span className="text-ink-muted">（{anchor.knowledge_point}）</span>
            </p>
            <Badge tone={anchorTone(anchor.status)}>
              {anchor.status === "confirmed" ? "锚点已确认" : anchor.status === "failed" ? "锚点失败" : "待确认"}
            </Badge>
          </div>
        ))}
      </div>
      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-3">
        <Button size="sm" onClick={onApprove} disabled={pending || hasFailedAnchor} title={hasFailedAnchor ? "存在失败锚点，请先锁定创意重出锚点" : undefined}>
          <CheckCircle2 className="size-3.5" aria-hidden />
          选定此方案
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setReviseOpen(true)} disabled={pending}>
          <PencilLine className="size-3.5" aria-hidden />
          修改
        </Button>
        {hasFailedAnchor ? (
          <Button size="sm" variant="secondary" onClick={onLockRedo} disabled={pending}>
            锁定创意重出锚点
          </Button>
        ) : null}
        <Button size="sm" variant="ghost" onClick={onDuplicate} disabled={pending} title="复制为自定义方案">
          <Copy className="size-3.5" aria-hidden />
        </Button>
      </div>

      <Dialog open={reviseOpen} onOpenChange={setReviseOpen}>
        <DialogContent title={`修改「${option.title}」`} description="只调整这一套方案，其余方案保持不变。">
          <FormField label="修改意见" required>
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={3}
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="例如：故事主角换成学生熟悉的动物形象。"
              />
            )}
          </FormField>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setReviseOpen(false)}>
              取消
            </Button>
            <Button
              disabled={instruction.trim().length === 0}
              onClick={() => {
                onRevise(instruction.trim());
                setReviseOpen(false);
                setInstruction("");
              }}
            >
              提交修改
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** 导入设计画布：三类九套方案 + 课程锚点 + 选定/修改/锁定重出。 */
export function IntroDesignCanvas({ workspace, onItemAction, itemActionPending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(introDesignContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="导入设计" />;

  return (
    <div className="space-y-6">
      {!content.selected_option_id ? (
        <p className="rounded-control bg-brand-selected px-3 py-2 text-sm text-brand">
          请从九套方案中选定一套作为该课时的导入创意；批准本步骤前必须完成选定。
        </p>
      ) : null}
      {content.categories.map((category) => (
        <section key={category.category_key}>
          <h3 className="mb-2.5 text-sm font-semibold text-ink-1">{category.category_name}</h3>
          <div className="grid gap-3 xl:grid-cols-3 lg:grid-cols-2">
            {category.options.map((option) => (
              <OptionCard
                key={option.option_id}
                option={option}
                selected={content.selected_option_id === option.option_id}
                pending={itemActionPending}
                onApprove={() => onItemAction({ itemId: option.option_id, action: "approve" })}
                onRevise={(instruction) => onItemAction({ itemId: option.option_id, action: "revise", instruction })}
                onLockRedo={() => onItemAction({ itemId: option.option_id, action: "lock_creative_redo_anchor" })}
                onDuplicate={() => onItemAction({ itemId: option.option_id, action: "duplicate_as_custom" })}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
