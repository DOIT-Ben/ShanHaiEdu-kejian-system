import { useState } from "react";
import { useNavigate, useOutletContext } from "react-router";
import { Archive, ArchiveRestore, Trash2 } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useArchiveProject, useDeleteProject, useRestoreProject, useUpdateProject } from "@/features/projects";
import { AppError } from "@/shared/api";
import {
  Button,
  ConfirmDialog,
  FormField,
  Input,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  RadioGroup,
  RadioGroupItem,
  Switch,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, ConflictDialog } from "@/widgets";
import { cn } from "@/shared/lib/cn";

const MODE_OPTIONS = [
  { value: "manual", label: "手动模式" },
  { value: "semi_auto", label: "半自动模式" },
  { value: "full_auto_draft", label: "全自动草稿模式" },
] as const;

/** 项目设置页：基本信息 / 执行模式 / 输出范围 / 预算 / 归档与删除。 */
export function ProjectSettingsPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const navigate = useNavigate();
  const update = useUpdateProject(project.project_id);
  const archive = useArchiveProject();
  const restore = useRestoreProject();
  const remove = useDeleteProject();

  const [name, setName] = useState(project.name);
  const [mode, setMode] = useState(project.execution_mode);
  const [scope, setScope] = useState({ ppt: project.output_scope?.ppt ?? true, video: project.output_scope?.video ?? true });
  const [budgetYuan, setBudgetYuan] = useState(String((project.budget_minor_units ?? 0) / 100));
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [conflictOpen, setConflictOpen] = useState(false);

  const save = () => {
    update.mutate(
      {
        name: name.trim(),
        execution_mode: mode,
        output_scope: scope,
        budget_minor_units: Math.round(Number(budgetYuan) * 100) || 0,
        row_version: project.row_version,
      },
      {
        onSuccess: () => toast({ tone: "success", title: "设置已保存" }),
        onError: (error) => {
          if (error instanceof AppError && error.status === 409) setConflictOpen(true);
        },
      },
    );
  };

  return (
    <div className="max-w-2xl space-y-4 p-6">
      <PageHeader title="项目设置" />

      <Panel>
        <PanelHeader title="基本设置" />
        <PanelBody className="space-y-4">
          <FormField label="项目名称" required>
            {({ id }) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} />}
          </FormField>
          <FormField label="执行模式" description="调整后对后续步骤生效，进行中的任务不受影响。">
            {() => (
              <RadioGroup value={mode} onValueChange={(value) => setMode(value as typeof mode)} className="flex flex-wrap gap-2">
                {MODE_OPTIONS.map((option) => (
                  <label
                    key={option.value}
                    className={cn(
                      "flex cursor-pointer items-center gap-2 rounded-control border px-3 py-2 text-sm",
                      mode === option.value ? "border-brand bg-brand-selected text-brand" : "border-line text-ink-2 hover:bg-surface-hover",
                    )}
                  >
                    <RadioGroupItem value={option.value} />
                    {option.label}
                  </label>
                ))}
              </RadioGroup>
            )}
          </FormField>
          <FormField label="输出内容">
            {() => (
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm text-ink-1">
                  <Switch checked={scope.ppt} onCheckedChange={(checked) => setScope((prev) => ({ ...prev, ppt: checked }))} />
                  课件 PPT
                </label>
                <label className="flex items-center gap-2 text-sm text-ink-1">
                  <Switch checked={scope.video} onCheckedChange={(checked) => setScope((prev) => ({ ...prev, video: checked }))} />
                  导入视频
                </label>
              </div>
            )}
          </FormField>
          <FormField label="项目预算（元）">
            {({ id }) => (
              <Input id={id} type="number" min={0} step={10} className="w-40" value={budgetYuan} onChange={(event) => setBudgetYuan(event.target.value)} />
            )}
          </FormField>
          {update.isError && !(update.error instanceof AppError && update.error.status === 409) ? (
            <AppErrorPanel error={update.error} title="保存失败" />
          ) : null}
          <div className="flex justify-end">
            <Button onClick={save} loading={update.isPending}>
              保存设置
            </Button>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="归档与删除" description="归档后项目变为只读，可随时恢复；删除不可恢复。" />
        <PanelBody className="flex flex-wrap gap-2">
          {project.status === "archived" ? (
            <Button
              variant="secondary"
              onClick={() => restore.mutate(project.project_id, { onSuccess: () => toast({ tone: "success", title: "项目已恢复" }) })}
              loading={restore.isPending}
            >
              <ArchiveRestore className="size-4" aria-hidden />
              恢复项目
            </Button>
          ) : (
            <Button
              variant="secondary"
              onClick={() =>
                archive.mutate(project.project_id, { onSuccess: () => toast({ tone: "success", title: "项目已归档" }) })
              }
              loading={archive.isPending}
            >
              <Archive className="size-4" aria-hidden />
              归档项目
            </Button>
          )}
          <Button variant="destructive" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="size-4" aria-hidden />
            删除项目
          </Button>
        </PanelBody>
      </Panel>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`删除项目「${project.name}」`}
        description="将永久删除项目及全部课时、产物与资产，且无法恢复。请输入理由以确认。"
        destructive
        requireReason
        loading={remove.isPending}
        confirmLabel="永久删除"
        onConfirm={() => {
          remove.mutate(project.project_id, {
            onSuccess: () => {
              toast({ tone: "success", title: "项目已删除" });
              void navigate("/app/projects");
            },
          });
        }}
      />

      <ConflictDialog
        open={conflictOpen}
        onOpenChange={setConflictOpen}
        serverRowVersion={
          update.error instanceof AppError
            ? ((update.error.details as { server_row_version?: number } | undefined)?.server_row_version ?? null)
            : null
        }
        onKeepMine={() => {
          setConflictOpen(false);
          const serverRowVersion =
            update.error instanceof AppError
              ? (update.error.details as { server_row_version?: number } | undefined)?.server_row_version
              : undefined;
          update.mutate(
            {
              name: name.trim(),
              execution_mode: mode,
              output_scope: scope,
              budget_minor_units: Math.round(Number(budgetYuan) * 100) || 0,
              row_version: serverRowVersion ?? project.row_version,
            },
            { onSuccess: () => toast({ tone: "success", title: "设置已保存" }) },
          );
        }}
        onUseServer={() => {
          setConflictOpen(false);
          setName(project.name);
          setMode(project.execution_mode);
          setScope({ ppt: project.output_scope?.ppt ?? true, video: project.output_scope?.video ?? true });
          setBudgetYuan(String((project.budget_minor_units ?? 0) / 100));
        }}
      />
    </div>
  );
}
