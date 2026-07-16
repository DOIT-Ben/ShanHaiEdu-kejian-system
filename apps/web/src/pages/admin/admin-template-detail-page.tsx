import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ArrowLeft, FlaskConical, History, Rocket, Undo2 } from "lucide-react";
import {
  usePublishTemplate,
  useRollbackTemplate,
  useTemplateDetail,
  useTemplateDryRun,
  useUpdateTemplate,
} from "@/features/admin";
import { useTask } from "@/features/tasks";
import { LESSON_NODES } from "@/entities/workflow/nodes";
import { formatRelativeTime } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  FormField,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Progress,
  Skeleton,
  Textarea,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, ValidationPanel } from "@/widgets";
import { TEMPLATE_STATUS_META } from "./admin-templates-page";

/** 模板详情页：内容编辑 / 干跑校验 / 发布 / 版本回滚。 */
export function AdminTemplateDetailPage() {
  const { templateId = "" } = useParams();
  const navigate = useNavigate();
  const detail = useTemplateDetail(templateId);
  const update = useUpdateTemplate(templateId);
  const dryRun = useTemplateDryRun(templateId);
  const publish = usePublishTemplate(templateId);
  const rollback = useRollbackTemplate(templateId);

  const [content, setContent] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);
  const [changelog, setChangelog] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [rollbackFor, setRollbackFor] = useState<string | null>(null);
  const [rollbackReason, setRollbackReason] = useState("");
  const [dryRunTaskId, setDryRunTaskId] = useState<string | null>(null);
  const dryRunTask = useTask(dryRunTaskId);

  useEffect(() => {
    setContent(detail.data?.content ?? "");
  }, [detail.data?.content]);

  useEffect(() => {
    if (dryRunTask.data && ["completed", "failed"].includes(dryRunTask.data.status)) {
      setDryRunTaskId(null);
      void detail.refetch();
      toast(
        dryRunTask.data.status === "completed"
          ? { tone: "success", title: "干跑完成", description: "校验结果已更新。" }
          : { tone: "danger", title: "干跑失败", description: dryRunTask.data.error?.message },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dryRunTask.data?.status]);

  if (detail.isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-96" />
      </div>
    );
  }
  if (detail.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={detail.error} title="模板加载失败" onRetry={() => void detail.refetch()} />
      </div>
    );
  }

  const data = detail.data;
  const template = data.template;
  const status = TEMPLATE_STATUS_META[template.status] ?? TEMPLATE_STATUS_META.draft;
  const dirty = content !== (data.content ?? "");
  const blockingErrors = data.validation_results.filter((result) => !result.passed && result.severity === "error");
  const dryRunning = dryRunTaskId !== null && Boolean(dryRunTask.data);

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => void navigate("/admin/templates")} aria-label="返回模板列表">
              <ArrowLeft className="size-4" aria-hidden />
            </Button>
            {template.name}
            <Badge tone={status.tone}>{status.label}</Badge>
          </span>
        }
        description={`${LESSON_NODES.find((node) => node.key === template.node_type)?.title ?? template.node_type} · 当前版本 ${template.current_version}`}
        actions={
          <>
            <Button variant="secondary" onClick={() => dryRun.mutate(undefined, { onSuccess: (task) => setDryRunTaskId(task.task_id) })} loading={dryRun.isPending || dryRunning}>
              <FlaskConical className="size-4" aria-hidden />
              干跑校验
            </Button>
            <Button
              onClick={() => setPublishOpen(true)}
              disabled={dirty}
              title={dirty ? "请先保存修改" : undefined}
            >
              <Rocket className="size-4" aria-hidden />
              发布
            </Button>
          </>
        }
      />

      {dryRunning && dryRunTask.data ? (
        <div className="rounded-panel border border-line bg-surface-1 px-5 py-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-ink-1">正在干跑校验…</p>
            <span className="text-sm tabular-nums text-ink-2">{Math.round(dryRunTask.data.progress_percent)}%</span>
          </div>
          <Progress className="mt-2" value={dryRunTask.data.progress_percent} />
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Panel>
          <PanelHeader
            title="模板内容"
            actions={
              dirty ? (
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={() => setContent(data.content ?? "")}>
                    放弃修改
                  </Button>
                  <Button
                    size="sm"
                    loading={update.isPending}
                    onClick={() =>
                      update.mutate({ content }, { onSuccess: () => toast({ tone: "success", title: "模板已保存为新草稿版本" }) })
                    }
                  >
                    保存修改
                  </Button>
                </div>
              ) : undefined
            }
          />
          <PanelBody>
            <Textarea
              rows={20}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="font-mono text-xs leading-5"
              aria-label="模板内容"
            />
            {update.isError ? <AppErrorPanel className="mt-3" error={update.error} title="保存失败" /> : null}
          </PanelBody>
        </Panel>

        <div className="space-y-4">
          <Panel>
            <PanelHeader title="校验结果" />
            <PanelBody>
              <ValidationPanel results={data.validation_results} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="版本历史" />
            <PanelBody>
              <ul className="space-y-1.5">
                {data.versions.map((version) => {
                  const meta = TEMPLATE_STATUS_META[version.status] ?? TEMPLATE_STATUS_META.draft;
                  return (
                    <li key={version.version} className="flex items-center gap-2 rounded-control border border-line px-3 py-2">
                      <History className="size-3.5 shrink-0 text-ink-muted" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-ink-1">{version.version}</p>
                        <p className="truncate text-xs text-ink-muted">
                          {version.changelog ?? ""} · {formatRelativeTime(version.created_at)}
                        </p>
                      </div>
                      <Badge tone={meta.tone}>{meta.label}</Badge>
                      {version.status !== "published" && version.version !== template.current_version ? null : version.version !==
                        template.current_version ? (
                        <Button size="sm" variant="ghost" onClick={() => setRollbackFor(version.version)}>
                          <Undo2 className="size-3.5" aria-hidden />
                          回滚
                        </Button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader title="节点绑定" />
            <PanelBody>
              {data.bindings.length === 0 ? (
                <p className="text-xs text-ink-muted">尚未绑定到工作流节点。</p>
              ) : (
                <ul className="space-y-1 text-sm text-ink-2">
                  {data.bindings.map((binding, index) => (
                    <li key={index}>
                      {LESSON_NODES.find((node) => node.key === binding.node_type)?.title ?? binding.node_type} · 工作流{" "}
                      {binding.workflow_version}
                      {binding.scope ? `（${binding.scope}）` : ""}
                    </li>
                  ))}
                </ul>
              )}
            </PanelBody>
          </Panel>
        </div>
      </div>

      {/* 发布确认 */}
      <Dialog open={publishOpen} onOpenChange={setPublishOpen}>
        <DialogContent
          title={`发布模板 ${template.current_version}`}
          description={
            blockingErrors.length > 0
              ? "存在未通过的阻断校验，发布需填写覆盖理由（将记入审计）。"
              : "发布后新生成将使用该版本模板。"
          }
        >
          <FormField label="变更说明" required>
            {({ id }) => (
              <Textarea id={id} rows={3} value={changelog} onChange={(event) => setChangelog(event.target.value)} placeholder="本次调整了……" />
            )}
          </FormField>
          {blockingErrors.length > 0 ? (
            <FormField label="覆盖理由" required description={`未通过校验：${blockingErrors.map((e) => e.message).join('；')}`}>
              {({ id }) => (
                <Textarea id={id} rows={2} value={overrideReason} onChange={(event) => setOverrideReason(event.target.value)} />
              )}
            </FormField>
          ) : null}
          {publish.isError ? <AppErrorPanel error={publish.error} title="发布失败" /> : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPublishOpen(false)}>
              取消
            </Button>
            <Button
              loading={publish.isPending}
              disabled={!changelog.trim() || (blockingErrors.length > 0 && !overrideReason.trim())}
              onClick={() =>
                publish.mutate(
                  {
                    version: template.current_version,
                    changelog: changelog.trim(),
                    override_reason: blockingErrors.length > 0 ? overrideReason.trim() : undefined,
                  },
                  {
                    onSuccess: () => {
                      toast({ tone: "success", title: "模板已发布" });
                      setPublishOpen(false);
                      setChangelog("");
                      setOverrideReason("");
                    },
                  },
                )
              }
            >
              确认发布
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 回滚确认 */}
      <Dialog open={rollbackFor !== null} onOpenChange={(open) => !open && setRollbackFor(null)}>
        <DialogContent title={`回滚到 ${rollbackFor}`} description="回滚后该版本会成为当前生效版本，操作会记入审计。">
          <FormField label="回滚理由" required>
            {({ id }) => (
              <Textarea id={id} rows={3} value={rollbackReason} onChange={(event) => setRollbackReason(event.target.value)} />
            )}
          </FormField>
          {rollback.isError ? <AppErrorPanel error={rollback.error} title="回滚失败" /> : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRollbackFor(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              loading={rollback.isPending}
              disabled={!rollbackReason.trim()}
              onClick={() => {
                if (!rollbackFor) return;
                rollback.mutate(
                  { to_version: rollbackFor, reason: rollbackReason.trim() },
                  {
                    onSuccess: () => {
                      toast({ tone: "success", title: `已回滚到 ${rollbackFor}` });
                      setRollbackFor(null);
                      setRollbackReason("");
                    },
                  },
                );
              }}
            >
              确认回滚
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
