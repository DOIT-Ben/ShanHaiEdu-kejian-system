import { useState, type ReactNode } from "react";
import { Dialog, DialogContent, DialogFooter } from "./dialog";
import { Button } from "./button";
import { Textarea } from "./textarea";
import { FormField } from "./form-field";

/**
 * 高风险操作二次确认对话框；可要求填写操作理由。
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "确认执行",
  cancelLabel = "取消",
  destructive,
  requireReason,
  loading,
  onConfirm,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  requireReason?: boolean;
  loading?: boolean;
  onConfirm: (reason: string) => void;
  children?: ReactNode;
}) {
  const [reason, setReason] = useState("");
  const reasonMissing = Boolean(requireReason) && reason.trim().length === 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setReason("");
        onOpenChange(next);
      }}
    >
      <DialogContent title={title} description={description}>
        {children}
        {requireReason ? (
          <FormField label="操作理由" required error={undefined}>
            {({ id, describedBy }) => (
              <Textarea
                id={id}
                aria-describedby={describedBy}
                rows={3}
                value={reason}
                placeholder="请说明执行该操作的原因（将进入审计记录）"
                onChange={(e) => setReason(e.target.value)}
              />
            )}
          </FormField>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            {cancelLabel}
          </Button>
          <Button
            variant={destructive ? "destructive" : "primary"}
            loading={loading}
            disabled={reasonMissing}
            onClick={() => onConfirm(reason.trim())}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
