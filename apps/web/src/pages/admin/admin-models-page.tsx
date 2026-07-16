import { useState } from "react";
import { useModels, useUpdateModel } from "@/features/admin";
import { Badge, Button, Dialog, DialogContent, DialogFooter, FormField, Input, PageHeader, Skeleton, Switch, Textarea, toast } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";
import type { ModelDefinition } from "@/shared/api/types";

function EditModelDialog({ model, onClose }: { model: ModelDefinition | null; onClose: () => void }) {
  const update = useUpdateModel();
  const [businessName, setBusinessName] = useState(model?.business_name ?? "");
  const [scenarios, setScenarios] = useState(model?.recommended_scenarios ?? "");
  return (
    <Dialog open={model !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`编辑 ${model?.business_name}`} description="业务名称与推荐场景面向教师展示；上游模型名仅管理员可见。">
        <div className="space-y-3">
          <FormField label="业务名称" required>
            {({ id }) => <Input id={id} value={businessName} onChange={(event) => setBusinessName(event.target.value)} />}
          </FormField>
          <FormField label="推荐场景">
            {({ id }) => <Textarea id={id} rows={2} value={scenarios} onChange={(event) => setScenarios(event.target.value)} />}
          </FormField>
          {update.isError ? <AppErrorPanel error={update.error} title="保存失败" /> : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            loading={update.isPending}
            disabled={!businessName.trim()}
            onClick={() => {
              if (!model) return;
              update.mutate(
                { modelId: model.model_id, patch: { business_name: businessName.trim(), recommended_scenarios: scenarios.trim() } },
                {
                  onSuccess: () => {
                    toast({ tone: "success", title: "模型配置已保存" });
                    onClose();
                  },
                },
              );
            }}
          >
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 能力模型配置页：业务名 / 上游名 / 能力标签 / 启停。 */
export function AdminModelsPage() {
  const models = useModels();
  const update = useUpdateModel();
  const [editing, setEditing] = useState<ModelDefinition | null>(null);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="能力与模型" description="登记各 Provider 的可用模型，配置面向教师的业务名称与推荐场景。" />

      {models.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : models.isError ? (
        <AppErrorPanel error={models.error} title="模型加载失败" onRetry={() => void models.refetch()} />
      ) : (
        <ul className="space-y-2">
          {(models.data ?? []).map((model) => (
            <li key={model.model_id} className="flex items-center gap-3 rounded-card border border-line bg-surface-1 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-ink-1">{model.business_name}</span>
                  <code className="rounded-control bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-ink-muted">
                    {model.upstream_name}
                  </code>
                  <span className="text-xs text-ink-muted">{model.provider_name ?? model.provider_id}</span>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-1.5">
                  {model.capabilities.map((capability) => (
                    <Badge key={capability} tone="neutral">
                      {capability}
                    </Badge>
                  ))}
                  {model.recommended_scenarios ? <span className="text-xs text-ink-muted">{model.recommended_scenarios}</span> : null}
                </div>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setEditing(model)}>
                编辑
              </Button>
              <label className="flex items-center gap-1.5 text-xs text-ink-2">
                <Switch
                  checked={model.enabled}
                  onCheckedChange={(checked) =>
                    update.mutate(
                      { modelId: model.model_id, patch: { enabled: checked } },
                      { onSuccess: () => toast({ tone: "success", title: checked ? "模型已启用" : "模型已停用" }) },
                    )
                  }
                  aria-label={`${model.enabled ? "停用" : "启用"} ${model.business_name}`}
                />
                {model.enabled ? "启用中" : "已停用"}
              </label>
            </li>
          ))}
        </ul>
      )}

      {editing ? <EditModelDialog key={editing.model_id} model={editing} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}
