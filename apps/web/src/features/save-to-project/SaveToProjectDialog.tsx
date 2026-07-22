import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Check, X } from "lucide-react";
import { useEffect, useRef, useState, type RefObject } from "react";
import {
  createMockSaveConflict,
  resolveMockSaveConflict,
  useMockRuntime,
} from "@/shared/api/mockClient";
import {
  listMockSavedResults,
  saveMockResult,
  type MockSavedResult,
  type MockSavedResultPreview,
  type MockSavedResultType,
} from "@/shared/api/mocks/savedResults";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";
import { Select } from "@/shared/ui/Select";
import { requiredItem } from "@/shared/lib/requiredItem";

export type SaveResultDescriptor = {
  id: string;
  preview?: MockSavedResultPreview;
  type: MockSavedResultType;
  title: string;
  lessonLabel?: string;
};

type SaveToProjectDialogProps = {
  allowedSlotKeys?: string[];
  customSlots?: SaveSlot[];
  lockSourceProject?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (result: MockSavedResult) => void;
  result: SaveResultDescriptor;
  returnFocusRef?: RefObject<HTMLElement | null>;
  sourceProjectId?: string;
};

type SaveSlot = {
  accepts: MockSavedResultType[];
  key: string;
  label: string;
};

const slots: SaveSlot[] = [
  { accepts: ["image"], key: "ppt.page-3.hero", label: "PPT 第 3 页主视觉（课堂讲解时显示）" },
  { accepts: ["image"], key: "video.shot-2", label: "课堂视频镜头 2（作为画面素材）" },
  { accepts: ["image"], key: "project.shared-images", label: "项目通用教学图片" },
  { accepts: ["video"], key: "video.intro", label: "课堂导入视频" },
  { accepts: ["video"], key: "project.shared-videos", label: "项目通用视频" },
  { accepts: ["ppt_page"], key: "ppt.full-deck", label: "当前课时课堂课件" },
  { accepts: ["ppt_page"], key: "project.shared-presentations", label: "项目通用课件" },
  { accepts: ["audio"], key: "project.shared-audio", label: "项目通用音频" },
  { accepts: ["document"], key: "project.documents", label: "项目文档" },
];

export function SaveConflictNotice({
  canAppendToShared,
  onModeChange,
  replaceMode,
}: {
  canAppendToShared: boolean;
  onModeChange: (mode: "replace" | "append") => void;
  replaceMode: "replace" | "append";
}) {
  return (
    <div className="rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-[var(--sh-ink-strong)]">
        <AlertTriangle aria-hidden="true" className="size-4 text-[var(--sh-warning)]" />
        该位置已有当前作品
      </p>
      <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
        替换会保留原版本，并提示受影响的 PPTX 重新导出。
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
            另存为项目通用素材
          </label>
        ) : null}
      </div>
    </div>
  );
}

export function SaveToProjectDialog({
  allowedSlotKeys,
  customSlots,
  lockSourceProject = false,
  onOpenChange,
  onSaved,
  open,
  result,
  returnFocusRef,
  sourceProjectId,
}: SaveToProjectDialogProps) {
  const runtime = useMockRuntime();
  const firstProjectId = runtime.projects[0]?.id ?? "";
  const availableSlots = (customSlots ?? slots).filter(
    (slot) =>
      slot.accepts.includes(result.type) &&
      (!allowedSlotKeys || allowedSlotKeys.includes(slot.key)),
  );
  const defaultSlot = requiredItem(availableSlots, 0, `${result.type} 对应的保存位置`);
  const canAppendToShared = availableSlots.some((slot) => slot.key.startsWith("project."));
  const [projectId, setProjectId] = useState(() => sourceProjectId ?? firstProjectId);
  const [slotKey, setSlotKey] = useState(defaultSlot.key);
  const [conflictId, setConflictId] = useState<string | null>(null);
  const [replaceMode, setReplaceMode] = useState<"replace" | "append">("replace");
  const returnFocusElement = useRef<HTMLElement | null>(null);
  const conflict = conflictId
    ? runtime.saveConflicts.find((item) => item.id === conflictId && item.status === "open")
    : undefined;

  useEffect(() => {
    if (!open) return;
    setProjectId(sourceProjectId ?? firstProjectId);
    setSlotKey(defaultSlot.key);
    setConflictId(null);
    setReplaceMode("replace");
  }, [defaultSlot.key, firstProjectId, open, sourceProjectId]);

  const abandonConflict = () => {
    if (conflictId) resolveMockSaveConflict(conflictId, "kept");
    setConflictId(null);
    setReplaceMode("replace");
  };

  const save = () => {
    if (!projectId) return;
    const occupied = listMockSavedResults(runtime, projectId).find(
      (savedResult) => savedResult.slotKey === slotKey && savedResult.resultId !== result.id,
    );
    if (!conflict && occupied) {
      const created = createMockSaveConflict({
        current_version: occupied.savedAt,
        project_id: projectId,
        requested_version: new Date().toISOString(),
        result_id: result.id,
        slot_key: slotKey,
      });
      setConflictId(created.id);
      return;
    }
    if (conflict) {
      resolveMockSaveConflict(conflict.id, replaceMode === "replace" ? "replaced" : "kept");
    }
    const appendToShared = Boolean(conflict && replaceMode === "append" && canAppendToShared);
    const sharedSlot = availableSlots.find((slot) => slot.key.startsWith("project."));
    const targetSlotKey = appendToShared
      ? `${sharedSlot?.key ?? defaultSlot.key}:${result.id}`
      : slotKey;
    const targetSlot = appendToShared
      ? (sharedSlot ?? defaultSlot)
      : (availableSlots.find((slot) => slot.key === targetSlotKey) ?? defaultSlot);
    const savedResult = saveMockResult({
      lessonLabel: result.lessonLabel ?? "独立创作",
      ...(result.preview ? { preview: result.preview } : {}),
      projectId,
      replaceMode,
      resultId: result.id,
      slotKey: targetSlotKey,
      slotLabel: targetSlot.label,
      title: result.title,
      type: result.type,
    });
    setConflictId(null);
    onSaved(savedResult);
    onOpenChange(false);
  };
  return (
    <Dialog.Root
      onOpenChange={(nextOpen) => {
        if (!nextOpen && conflictId) abandonConflict();
        onOpenChange(nextOpen);
      }}
      open={open}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
        <Dialog.Content
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
                保存后作品才会进入项目的素材与成果。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton label="关闭">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div className="mt-6 space-y-4">
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">目标项目</span>
              {lockSourceProject && sourceProjectId ? (
                <div className="mt-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-soft)] px-3 py-2.5 text-sm">
                  {runtime.projects.find((project) => project.id === sourceProjectId)?.title ??
                    "来源项目"}
                </div>
              ) : (
                <Select
                  ariaLabel="目标项目"
                  className="mt-2 w-full"
                  onValueChange={(nextProjectId) => {
                    abandonConflict();
                    setProjectId(nextProjectId);
                  }}
                  options={runtime.projects.map((project) => ({
                    label: project.title,
                    value: project.id,
                  }))}
                  value={projectId}
                />
              )}
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-[var(--sh-ink-strong)]">保存位置</span>
              <Select
                ariaLabel="保存位置"
                className="mt-2 w-full"
                onValueChange={(nextSlotKey) => {
                  abandonConflict();
                  setSlotKey(nextSlotKey);
                }}
                options={availableSlots.map((slot) => ({ label: slot.label, value: slot.key }))}
                value={slotKey}
              />
            </label>
            {conflict ? (
              <SaveConflictNotice
                canAppendToShared={canAppendToShared}
                onModeChange={setReplaceMode}
                replaceMode={replaceMode}
              />
            ) : null}
          </div>
          <div className="mt-7 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="quiet">取消</Button>
            </Dialog.Close>
            <Button disabled={!projectId} onClick={save}>
              <Check aria-hidden="true" />
              {conflict ? "确认保存" : "保存到这个位置"}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
