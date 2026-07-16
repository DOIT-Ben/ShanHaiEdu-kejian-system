import { useState } from "react";
import { CheckCircle2, PencilLine } from "lucide-react";
import type { NodeWorkspace, ValidationResult } from "@/shared/api/types";
import { Button, Checkbox, Dialog, DialogContent, DialogFooter, FormField, Textarea } from "@/shared/ui";
import type { NodeStatus } from "@/shared/lib/status";

/**
 * 审批操作条：批准当前版本 / 提交修改意见（修订）。
 * 存在未确认警告时批准前必须逐项确认并填写说明。
 */
export function ApprovalBar({
  workspace,
  approving,
  revising,
  onApprove,
  onRevise,
}: {
  workspace: NodeWorkspace;
  approving?: boolean;
  revising?: boolean;
  onApprove: (input: { versionId: string; overrideWarningRuleIds?: string[]; overrideReason?: string }) => void;
  onRevise: (instruction: string) => void;
}) {
  const [reviseOpen, setReviseOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [warningOpen, setWarningOpen] = useState(false);
  const [checkedRules, setCheckedRules] = useState<Set<string>>(new Set());
  const [overrideReason, setOverrideReason] = useState("");

  const latest = workspace.artifact_versions[0];
  const nodeStatus = workspace.node.status as NodeStatus;
  if (!latest || !["needs_review", "revision_required", "stale"].includes(nodeStatus)) return null;

  const warnings: ValidationResult[] = (workspace.validation_results ?? []).filter((v) => !v.passed && v.severity === "warning");
  const blockingErrors = (workspace.validation_results ?? []).filter((v) => !v.passed && v.severity === "error");

  const submitApprove = () => {
    if (warnings.length > 0) {
      setWarningOpen(true);
      return;
    }
    onApprove({ versionId: latest.artifact_version_id });
  };

  const confirmWarnings = () => {
    onApprove({
      versionId: latest.artifact_version_id,
      overrideWarningRuleIds: [...checkedRules],
      overrideReason: overrideReason.trim(),
    });
    setWarningOpen(false);
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-panel border border-line bg-surface-1 px-4 py-3">
      <p className="text-sm text-ink-2">
        当前为第 {latest.version_number} 版
        {blockingErrors.length > 0 ? (
          <span className="ml-2 text-danger">有 {blockingErrors.length} 项校验未通过，暂时不能批准</span>
        ) : warnings.length > 0 ? (
          <span className="ml-2 text-warning">有 {warnings.length} 项警告需在批准时确认</span>
        ) : (
          <span className="ml-2 text-ink-muted">确认无误后批准，下游步骤将解锁</span>
        )}
      </p>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => setReviseOpen(true)} loading={revising}>
          <PencilLine className="size-4" aria-hidden />
          提交修改意见
        </Button>
        <Button size="sm" onClick={submitApprove} loading={approving} disabled={blockingErrors.length > 0}>
          <CheckCircle2 className="size-4" aria-hidden />
          批准此版本
        </Button>
      </div>

      <Dialog open={reviseOpen} onOpenChange={setReviseOpen}>
        <DialogContent
          title="提交修改意见"
          description="系统会基于当前版本和你的意见生成新版本，原版本保留在版本历史中。"
        >
          <FormField label="修改意见" required>
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={4}
                value={instruction}
                onChange={(event) => setInstruction(event.target.value)}
                placeholder="例如：导入环节的提问再贴近生活一些，把例子换成分披萨。"
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
              生成修订版
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={warningOpen} onOpenChange={setWarningOpen}>
        <DialogContent title="确认校验警告" description="以下警告不阻断批准，但需要你逐项确认并说明理由（将进入审计记录）。">
          <div className="space-y-2">
            {warnings.map((warning) => (
              <label key={warning.rule_id} className="flex items-start gap-2 rounded-control border border-line px-3 py-2">
                <Checkbox
                  checked={checkedRules.has(warning.rule_id)}
                  onCheckedChange={(checked) => {
                    setCheckedRules((prev) => {
                      const next = new Set(prev);
                      if (checked) next.add(warning.rule_id);
                      else next.delete(warning.rule_id);
                      return next;
                    });
                  }}
                />
                <span className="text-sm text-ink-1">{warning.message}</span>
              </label>
            ))}
          </div>
          <FormField label="确认说明" required className="mt-3">
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={2}
                value={overrideReason}
                onChange={(event) => setOverrideReason(event.target.value)}
                placeholder="说明为什么可以带警告批准。"
              />
            )}
          </FormField>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setWarningOpen(false)}>
              取消
            </Button>
            <Button
              disabled={checkedRules.size < warnings.length || overrideReason.trim().length === 0}
              onClick={confirmWarnings}
            >
              确认并批准
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
