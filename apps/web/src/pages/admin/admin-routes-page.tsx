import { useState } from "react";
import { FlaskConical, Pencil, Plus } from "lucide-react";
import { useModels, useRoutes, useSaveRoute, useSimulateRoute, type RouteCreateBody } from "@/features/admin";
import type { RoutePolicy, RouteSimulation } from "@/shared/api/types";
import { formatMinorUnits } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  FormField,
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Switch,
  toast,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const MODE_LABEL: Record<RoutePolicy["mode"], string> = {
  quality: "质量优先",
  economy: "经济优先",
  speed: "速度优先",
  balanced: "均衡",
  fixed: "固定模型",
};

const CAPABILITIES = ["text_generation", "image_generation", "video_generation", "tts", "pptx_render"];

function RouteFormDialog({ policy, onClose }: { policy: RoutePolicy | "new" | null; onClose: () => void }) {
  const models = useModels();
  const save = useSaveRoute();
  const simulate = useSimulateRoute();
  const editing = policy !== null && policy !== "new" ? policy : null;
  const [form, setForm] = useState<RouteCreateBody>({
    capability: editing?.capability ?? "text_generation",
    mode: editing?.mode ?? "balanced",
    primary_model_id: editing?.primary_model_id ?? "",
    fallback_model_ids: editing?.fallback_model_ids ?? [],
    allow_cross_provider_fallback: editing?.allow_cross_provider_fallback ?? true,
    max_cost_minor_units: editing?.max_cost_minor_units ?? null,
    enabled: editing?.enabled ?? true,
  });
  const [simulation, setSimulation] = useState<RouteSimulation | null>(null);

  const capabilityModels = (models.data ?? []).filter((model) => model.capabilities.includes(form.capability));

  return (
    <Dialog open={policy !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={editing ? `编辑路由：${editing.capability}` : "新增路由策略"} className="max-w-xl">
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="能力" required>
              {({ id }) => (
                <Select
                  value={form.capability}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, capability: value, primary_model_id: "", fallback_model_ids: [] }))}
                >
                  <SelectTrigger id={id} disabled={editing !== null}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CAPABILITIES.map((capability) => (
                      <SelectItem key={capability} value={capability}>
                        {capability}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>
            <FormField label="路由模式" required>
              {({ id }) => (
                <Select value={form.mode} onValueChange={(value) => setForm((prev) => ({ ...prev, mode: value as RoutePolicy["mode"] }))}>
                  <SelectTrigger id={id}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(MODE_LABEL).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>
          </div>
          <FormField label="主选模型" required>
            {({ id }) => (
              <Select value={form.primary_model_id} onValueChange={(value) => setForm((prev) => ({ ...prev, primary_model_id: value }))}>
                <SelectTrigger id={id}>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {capabilityModels.map((model) => (
                    <SelectItem key={model.model_id} value={model.model_id}>
                      {model.business_name}（{model.provider_name ?? model.provider_id}）
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField label="备选链" description="主选失败时按顺序尝试。点击切换选中。">
            {() => (
              <div className="flex flex-wrap gap-1.5">
                {capabilityModels
                  .filter((model) => model.model_id !== form.primary_model_id)
                  .map((model) => {
                    const selected = form.fallback_model_ids.includes(model.model_id);
                    return (
                      <button
                        key={model.model_id}
                        type="button"
                        onClick={() =>
                          setForm((prev) => ({
                            ...prev,
                            fallback_model_ids: selected
                              ? prev.fallback_model_ids.filter((id) => id !== model.model_id)
                              : [...prev.fallback_model_ids, model.model_id],
                          }))
                        }
                        className={
                          selected
                            ? "rounded-control border border-brand bg-brand-selected px-2.5 py-1 text-xs text-brand"
                            : "rounded-control border border-line px-2.5 py-1 text-xs text-ink-2 hover:bg-surface-hover"
                        }
                      >
                        {selected ? `${form.fallback_model_ids.indexOf(model.model_id) + 1}. ` : ""}
                        {model.business_name}
                      </button>
                    );
                  })}
              </div>
            )}
          </FormField>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="单次调用费用上限（分）">
              {({ id }) => (
                <Input
                  id={id}
                  type="number"
                  min={0}
                  value={form.max_cost_minor_units ?? ""}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, max_cost_minor_units: event.target.value ? Number(event.target.value) : null }))
                  }
                />
              )}
            </FormField>
            <FormField label="允许跨 Provider 备选">
              {() => (
                <div className="pt-1.5">
                  <Switch
                    checked={form.allow_cross_provider_fallback ?? false}
                    onCheckedChange={(checked) => setForm((prev) => ({ ...prev, allow_cross_provider_fallback: checked }))}
                  />
                </div>
              )}
            </FormField>
          </div>

          {simulation ? (
            <div className="rounded-control border border-line bg-surface-2 px-3 py-2.5 text-sm">
              <p className="text-ink-1">
                命中：<span className="font-medium">{simulation.selected_model_name}</span>
                {simulation.provider_name ? `（${simulation.provider_name}）` : ""}
              </p>
              {simulation.fallback_chain.length > 0 ? (
                <p className="mt-0.5 text-xs text-ink-2">备选链：{simulation.fallback_chain.join(" → ")}</p>
              ) : null}
              {simulation.estimated_cost_note ? <p className="mt-0.5 text-xs text-ink-muted">{simulation.estimated_cost_note}</p> : null}
              {simulation.conflicts.length > 0 ? (
                <ul className="mt-1 list-inside list-disc text-xs text-warning">
                  {simulation.conflicts.map((conflict, index) => (
                    <li key={index}>{conflict}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          {save.isError ? <AppErrorPanel error={save.error} title="保存失败" /> : null}
          {simulate.isError ? <AppErrorPanel error={simulate.error} title="模拟失败" /> : null}
        </div>
        <DialogFooter>
          <Button
            variant="secondary"
            loading={simulate.isPending}
            disabled={!form.primary_model_id}
            onClick={() =>
              simulate.mutate(
                {
                  capability: form.capability,
                  mode: form.mode,
                  primary_model_id: form.primary_model_id,
                  fallback_model_ids: form.fallback_model_ids,
                },
                { onSuccess: setSimulation },
              )
            }
          >
            <FlaskConical className="size-4" aria-hidden />
            模拟命中
          </Button>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            loading={save.isPending}
            disabled={!form.primary_model_id}
            onClick={() =>
              save.mutate(
                { routePolicyId: editing?.route_policy_id, body: form },
                {
                  onSuccess: () => {
                    toast({ tone: "success", title: "路由策略已保存" });
                    onClose();
                  },
                },
              )
            }
          >
            保存策略
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 路由策略页：能力级模型选择规则 + 备选链 + 模拟。 */
export function AdminRoutesPage() {
  const routes = useRoutes();
  const models = useModels();
  const save = useSaveRoute();
  const [dialogFor, setDialogFor] = useState<RoutePolicy | "new" | null>(null);

  const modelName = (modelId: string) => (models.data ?? []).find((model) => model.model_id === modelId)?.business_name ?? modelId;

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="路由策略"
        description="决定每个生成能力实际使用哪个模型，以及失败时的备选顺序。"
        actions={
          <Button onClick={() => setDialogFor("new")}>
            <Plus className="size-4" aria-hidden />
            新增策略
          </Button>
        }
      />

      {routes.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : routes.isError ? (
        <AppErrorPanel error={routes.error} title="路由加载失败" onRetry={() => void routes.refetch()} />
      ) : (
        <ul className="space-y-2">
          {(routes.data ?? []).map((policy) => (
            <li key={policy.route_policy_id} className="flex items-center gap-3 rounded-card border border-line bg-surface-1 px-4 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-ink-1">{policy.capability}</span>
                  <Badge tone="brand">{MODE_LABEL[policy.mode]}</Badge>
                  {policy.max_cost_minor_units ? (
                    <span className="text-xs text-ink-muted">上限 {formatMinorUnits(policy.max_cost_minor_units)}</span>
                  ) : null}
                </div>
                <p className="mt-1 text-xs text-ink-muted">
                  主选 {modelName(policy.primary_model_id)}
                  {policy.fallback_model_ids.length > 0 ? ` → 备选 ${policy.fallback_model_ids.map(modelName).join(" → ")}` : "（无备选）"}
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => setDialogFor(policy)}>
                <Pencil className="size-3.5" aria-hidden />
                编辑
              </Button>
              <label className="flex items-center gap-1.5 text-xs text-ink-2">
                <Switch
                  checked={policy.enabled}
                  onCheckedChange={(checked) =>
                    save.mutate(
                      {
                        routePolicyId: policy.route_policy_id,
                        body: {
                          capability: policy.capability,
                          mode: policy.mode,
                          primary_model_id: policy.primary_model_id,
                          fallback_model_ids: policy.fallback_model_ids,
                          allow_cross_provider_fallback: policy.allow_cross_provider_fallback,
                          max_cost_minor_units: policy.max_cost_minor_units,
                          enabled: checked,
                        },
                      },
                      { onSuccess: () => toast({ tone: "success", title: checked ? "策略已启用" : "策略已停用" }) },
                    )
                  }
                  aria-label={`${policy.enabled ? "停用" : "启用"}路由 ${policy.capability}`}
                />
                {policy.enabled ? "启用中" : "已停用"}
              </label>
            </li>
          ))}
        </ul>
      )}

      {dialogFor !== null ? (
        <RouteFormDialog
          key={dialogFor === "new" ? "new" : dialogFor.route_policy_id}
          policy={dialogFor}
          onClose={() => setDialogFor(null)}
        />
      ) : null}
    </div>
  );
}
