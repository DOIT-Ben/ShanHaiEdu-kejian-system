import { useState } from "react";
import { CheckCircle2, MessageSquareText } from "lucide-react";
import { useApproveArtifact, useRequestChanges } from "@/features/node-runs";
import type { ValidationIssue } from "@/shared/api";
import {
  Button,
  Checkbox,
  Dialog,
  DialogContent,
  DialogFooter,
  Textarea,
  toast,
} from "@/shared/ui";

/**
 * 审批操作（02 §6）：批准（校验警告须逐条确认并填写说明）+ 要求修改（局部返修）。
 * 一个区域只有一个主操作：批准为主，其余次级。
 */
export function ApprovalActions({
  versionId,
  nodeRunId,
  validationIssues,
  approveLabel = "确认这一版",
  onApproved,
}: {
  versionId: string;
  nodeRunId: string | null;
  validationIssues: ValidationIssue[];
  approveLabel?: string;
  onApproved?: () => void;
}) {
  const approve = useApproveArtifact(versionId, nodeRunId);
  const requestChanges = useRequestChanges(versionId, nodeRunId);
  const warnings = validationIssues.filter((issue) => issue.severity === "warning");
  const errors = validationIssues.filter((issue) => issue.severity === "error");
  const [warningOpen, setWarningOpen] = useState(false);
  const [changesOpen, setChangesOpen] = useState(false);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [ackNote, setAckNote] = useState("");
  const [instruction, setInstruction] = useState("");

  const doApprove = (input?: { keys: string[]; note: string }) => {
    approve.mutate(
      input
        ? { acknowledgedWarningKeys: input.keys, acknowledgementNote: input.note }
        : undefined,
      {
        onSuccess: () => {
          setWarningOpen(false);
          toast({ tone: "success", title: "已确认", description: "这一版已批准，可以进入下一步。" });
          onApproved?.();
        },
        onError: (error) => toast({ tone: "danger", title: "批准失败", description: error.message }),
      },
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        loading={approve.isPending}
        loadingText="正在确认…"
        disabled={errors.length > 0}
        title={errors.length > 0 ? "存在必须修复的问题，暂不能批准" : undefined}
        onClick={() => {
          if (warnings.length > 0) {
            setAcknowledged(new Set());
            setAckNote("");
            setWarningOpen(true);
          } else {
            doApprove();
          }
        }}
      >
        <CheckCircle2 className="size-4" aria-hidden />
        {approveLabel}
      </Button>
      <Button variant="outline" onClick={() => setChangesOpen(true)}>
        <MessageSquareText className="size-4" aria-hidden />
        要求修改
      </Button>

      <Dialog open={warningOpen} onOpenChange={setWarningOpen}>
        <DialogContent
          title="确认校验提醒"
          description="以下提醒需要你逐条确认。确认后仍会保留在记录中。"
        >
          <ul className="space-y-2.5">
            {warnings.map((warning) => (
              <li key={warning.key} className="flex items-start gap-2.5 rounded-md border border-warning-200 bg-warning-50 p-3">
                <Checkbox
                  id={`ack-${warning.key}`}
                  checked={acknowledged.has(warning.key)}
                  onCheckedChange={(checked) => {
                    setAcknowledged((prev) => {
                      const next = new Set(prev);
                      if (checked === true) next.add(warning.key);
                      else next.delete(warning.key);
                      return next;
                    });
                  }}
                />
                <label htmlFor={`ack-${warning.key}`} className="text-sm leading-relaxed text-ink">
                  {warning.message}
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <label htmlFor="ack-note" className="text-sm font-medium text-ink-strong">
              确认说明<span className="ml-0.5 text-danger">*</span>
            </label>
            <Textarea
              id="ack-note"
              className="mt-1.5"
              rows={2}
              placeholder="例如：环节时长符合本班实际，保持现状。"
              value={ackNote}
              onChange={(e) => setAckNote(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setWarningOpen(false)}>
              再看看
            </Button>
            <Button
              disabled={acknowledged.size < warnings.length || !ackNote.trim()}
              loading={approve.isPending}
              loadingText="正在确认…"
              onClick={() => doApprove({ keys: [...acknowledged], note: ackNote.trim() })}
            >
              确认并批准
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={changesOpen} onOpenChange={setChangesOpen}>
        <DialogContent
          title="要求修改"
          description="说明需要修改什么。系统会基于当前版本做局部调整，不会推翻你已确认的内容。"
        >
          <Textarea
            rows={4}
            placeholder="例如：把第二个环节的活动换成小组操作，时长压缩到 10 分钟。"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            aria-label="修改要求"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setChangesOpen(false)}>
              取消
            </Button>
            <Button
              disabled={!instruction.trim()}
              loading={requestChanges.isPending}
              loadingText="正在提交…"
              onClick={() =>
                requestChanges.mutate(
                  { instruction: instruction.trim() },
                  {
                    onSuccess: () => {
                      setChangesOpen(false);
                      setInstruction("");
                      toast({ tone: "success", title: "修改要求已提交", description: "生成完成后会回到这里等你确认。" });
                    },
                    onError: (error) => toast({ tone: "danger", title: "提交失败", description: error.message }),
                  },
                )
              }
            >
              提交修改要求
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
