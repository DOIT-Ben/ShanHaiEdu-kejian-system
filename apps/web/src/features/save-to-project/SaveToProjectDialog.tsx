import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Check, X } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";
import { Select } from "@/shared/ui/Select";

export type SaveResultType = "image" | "ppt_page" | "video" | "audio" | "document";

export type SaveResultPreview = {
  candidate: number;
  generation: number;
  ratio: string;
};

export type SaveResultDescriptor = {
  id: string;
  preview?: SaveResultPreview;
  type: SaveResultType;
  title: string;
  lessonLabel?: string;
};

export type SaveProjectOption = {
  id: string;
  title: string;
};

export type SaveSlot = {
  accepts: SaveResultType[];
  key: string;
  label: string;
};

export type SaveReplaceMode = "reject_if_occupied" | "replace_active" | "append";

export type SaveToProjectIntent = {
  projectId: string;
  replaceMode: SaveReplaceMode;
  result: SaveResultDescriptor;
  slotKey: string;
};

export type SaveConflict = {
  canAppend: boolean;
  message?: string;
};

export type SaveToProjectDialogProps = {
  busy?: boolean;
  conflict?: SaveConflict;
  errorMessage?: string;
  lockSourceProject?: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (intent: SaveToProjectIntent) => void;
  open: boolean;
  projects: readonly SaveProjectOption[];
  result: SaveResultDescriptor;
  returnFocusRef?: RefObject<HTMLElement | null>;
  slots: readonly SaveSlot[];
  sourceProjectId?: string;
};

export function SaveConflictNotice({
  canAppendToShared,
  message,
  onModeChange,
  replaceMode,
}: {
  canAppendToShared: boolean;
  message?: string;
  onModeChange: (mode: "replace" | "append") => void;
  replaceMode: "replace" | "append";
}) {
  return (
    <div className="rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-[var(--sh-ink-strong)]">
        <AlertTriangle aria-hidden="true" className="size-4 text-[var(--sh-warning)]" />
        {message ?? "该位置已有当前作品"}
      </p>
      <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
        替换会停用当前绑定，并保留原有版本记录。
      </p>
      <div className="mt-3 grid gap-2">
        <label className="flex cursor-pointer items-center gap-2 rounded-md bg-[var(--sh-surface-elevated)] p-3 text-sm">
          <input
            checked={replaceMode === "replace"}
            onChange={() => onModeChange("replace")}
            type="radio"
          />
          替换当前版本，保留历史
        </label>
        {canAppendToShared ? (
          <label className="flex cursor-pointer items-center gap-2 rounded-md bg-[var(--sh-surface-elevated)] p-3 text-sm">
            <input
              checked={replaceMode === "append"}
              onChange={() => onModeChange("append")}
              type="radio"
            />
            追加到这个保存位置
          </label>
        ) : null}
      </div>
    </div>
  );
}

export function SaveToProjectDialog({
  busy = false,
  conflict,
  errorMessage,
  lockSourceProject = false,
  onOpenChange,
  onSave,
  open,
  projects,
  result,
  returnFocusRef,
  slots,
  sourceProjectId,
}: SaveToProjectDialogProps) {
  const availableSlots = slots.filter((slot) => slot.accepts.includes(result.type));
  const firstProjectId = projects[0]?.id ?? "";
  const firstSlotKey = availableSlots[0]?.key ?? "";
  const [projectId, setProjectId] = useState(() => sourceProjectId ?? firstProjectId);
  const [slotKey, setSlotKey] = useState(firstSlotKey);
  const [replaceMode, setReplaceMode] = useState<"replace" | "append">("replace");
  const returnFocusElement = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    setProjectId(sourceProjectId ?? firstProjectId);
    setSlotKey(firstSlotKey);
    setReplaceMode("replace");
  }, [firstProjectId, firstSlotKey, open, sourceProjectId]);

  const save = () => {
    if (!projectId || !slotKey || busy) return;
    onSave({
      projectId,
      replaceMode: conflict
        ? replaceMode === "append"
          ? "append"
          : "replace_active"
        : "reject_if_occupied",
      result,
      slotKey,
    });
  };

  const lockedProjectTitle = projects.find((project) => project.id === sourceProjectId)?.title;
  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
        <Dialog.Content
          aria-busy={busy}
          className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,520px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)]"
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            (returnFocusRef?.current ?? returnFocusElement.current)?.focus();
          }}
          onEscapeKeyDown={() => onOpenChange(false)}
          onOpenAutoFocus={() => {
            returnFocusElement.current =
              document.activeElement instanceof HTMLElement ? document.activeElement : null;
          }}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-bold text-[var(--sh-ink-strong)]">
                保存到项目
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                确认目标项目和保存位置后再提交。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton disabled={busy} label="关闭">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div className="mt-6 space-y-4">
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">目标项目</span>
              {lockSourceProject && sourceProjectId ? (
                <div className="mt-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-soft)] px-3 py-2.5 text-sm">
                  {lockedProjectTitle ?? "来源项目"}
                </div>
              ) : (
                <Select
                  ariaLabel="目标项目"
                  className="mt-2 w-full"
                  disabled={busy}
                  onValueChange={setProjectId}
                  options={projects.map((project) => ({ label: project.title, value: project.id }))}
                  value={projectId}
                />
              )}
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">保存位置</span>
              <Select
                ariaLabel="保存位置"
                className="mt-2 w-full"
                disabled={busy}
                onValueChange={setSlotKey}
                options={availableSlots.map((slot) => ({ label: slot.label, value: slot.key }))}
                value={slotKey}
              />
            </label>
            {availableSlots.length === 0 ? (
              <p className="text-sm text-[var(--sh-danger)]" role="alert">
                当前作品没有可用的保存位置。
              </p>
            ) : null}
            {conflict ? (
              <SaveConflictNotice
                canAppendToShared={conflict.canAppend}
                message={conflict.message}
                onModeChange={setReplaceMode}
                replaceMode={replaceMode}
              />
            ) : null}
            {errorMessage ? (
              <p className="text-sm text-[var(--sh-danger)]" role="alert">
                {errorMessage}
              </p>
            ) : null}
          </div>
          <div className="mt-7 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button disabled={busy} variant="quiet">
                取消
              </Button>
            </Dialog.Close>
            <Button disabled={busy || !projectId || !slotKey} onClick={save}>
              <Check aria-hidden="true" />
              {busy ? "正在保存" : conflict ? "确认保存" : "保存到这个位置"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
