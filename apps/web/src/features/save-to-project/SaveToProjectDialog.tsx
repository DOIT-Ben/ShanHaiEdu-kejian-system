import { useState } from "react";
import { FolderInput } from "lucide-react";
import { AppError } from "@/shared/api";
import { useProjects } from "@/features/projects";
import {
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  FormField,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  toast,
} from "@/shared/ui";
import { useSaveToProject, type ReplaceMode } from "./api";

export interface SaveOutcome {
  bindingId: string;
  clipId: string | null;
  savedTo: { projectTitle: string; slotLabel: string };
}

/**
 * 保存到项目对话框（05 统一业务组件 SaveToProjectDialog）：
 * 目标位置默认给出；槽位被占用时给出「替换 / 另存新版本 / 取消」三选。
 */
export function SaveToProjectDialog({
  open,
  onOpenChange,
  resultId,
  defaultProjectId,
  defaultSlotKey,
  slotLabel,
  lockTarget = false,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resultId: string | null;
  defaultProjectId: string | null;
  defaultSlotKey: string;
  slotLabel: string;
  /** 项目内工作台调用时目标固定，不允许改保存位置。 */
  lockTarget?: boolean;
  onSaved?: (outcome: SaveOutcome) => void;
}) {
  const { data: projects } = useProjects();
  const save = useSaveToProject();
  const [projectId, setProjectId] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ title: string; versionNo: number } | null>(null);

  const effectiveProject = projectId ?? defaultProjectId ?? "";
  const effectiveSlot = defaultSlotKey;

  const doSave = (mode: ReplaceMode) => {
    if (!resultId || !effectiveProject) return;
    save.mutate(
      { resultId, projectId: effectiveProject, slotKey: effectiveSlot, replaceMode: mode },
      {
        onSuccess: (data) => {
          setConflict(null);
          onOpenChange(false);
          const projectTitle = data.saved_to?.project_title ?? "项目";
          toast({
            tone: "success",
            title: "已保存到项目",
            description: `已保存到「${projectTitle}」的${data.saved_to?.slot_label ?? slotLabel}。`,
          });
          onSaved?.({
            bindingId: data.binding_id,
            clipId: data.clip_id ?? null,
            savedTo: { projectTitle, slotLabel: data.saved_to?.slot_label ?? slotLabel },
          });
        },
        onError: (error) => {
          if (error instanceof AppError && error.isSlotOccupied) {
            const occupied = (error.details?.occupied_by ?? {}) as { title?: string; version_no?: number };
            setConflict({ title: occupied.title ?? "已有内容", versionNo: occupied.version_no ?? 1 });
            return;
          }
          toast({ tone: "danger", title: "保存失败", description: error.message });
        },
      },
    );
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) setConflict(null);
        onOpenChange(next);
      }}
    >
      <DialogContent title="保存到项目" description={`保存后可在项目的「素材与成果」里找到。`}>
        {conflict ? (
          <div className="space-y-4">
            <div className="rounded-md border border-warning-200 bg-warning-50 p-3.5 text-sm text-ink">
              目标位置已有「{conflict.title}」（第 {conflict.versionNo} 版）。要怎么处理？
            </div>
            <div className="grid gap-2">
              <Button
                variant="outline"
                loading={save.isPending}
                onClick={() => doSave("replace_active")}
                className="justify-start"
              >
                替换当前使用的版本（旧版本保留在历史里）
              </Button>
              <Button
                variant="outline"
                loading={save.isPending}
                onClick={() => doSave("append")}
                className="justify-start"
              >
                另存为新版本（不改变当前使用的版本）
              </Button>
              <Button variant="ghost" onClick={() => setConflict(null)} className="justify-start">
                返回
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="space-y-4">
              <FormField label="保存到项目">
                {({ id }) =>
                  lockTarget ? (
                    <p id={id} className="rounded-md bg-surface-soft px-3 py-2 text-sm text-ink">
                      {projects?.find((p) => p.id === effectiveProject)?.title ?? "当前项目"}
                    </p>
                  ) : (
                    <Select value={effectiveProject} onValueChange={setProjectId}>
                      <SelectTrigger id={id} aria-label="选择项目">
                        <SelectValue placeholder="选择项目" />
                      </SelectTrigger>
                      <SelectContent>
                        {(projects ?? []).map((project) => (
                          <SelectItem key={project.id} value={project.id}>
                            {project.title}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )
                }
              </FormField>
              <FormField label="保存位置">
                {({ id }) => (
                  <p id={id} className="rounded-md bg-surface-soft px-3 py-2 text-sm text-ink">
                    {slotLabel}
                  </p>
                )}
              </FormField>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                取消
              </Button>
              <Button
                disabled={!resultId || !effectiveProject}
                loading={save.isPending}
                loadingText="正在保存…"
                onClick={() => doSave("reject_if_occupied")}
              >
                <FolderInput className="size-4" aria-hidden />
                保存到项目
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
