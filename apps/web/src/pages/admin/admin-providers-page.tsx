import { useEffect, useState } from "react";
import { KeyRound, Plug, Plus, ShieldCheck } from "lucide-react";
import {
  useCreateProvider,
  useProviders,
  useTestProviderConnection,
  useUpdateProvider,
  type ProviderCreateBody,
} from "@/features/admin";
import { useTask } from "@/features/tasks";
import type { Provider } from "@/shared/api/types";
import { formatRelativeTime } from "@/shared/lib/format";
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

const HEALTH_META: Record<Provider["health_status"], { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  healthy: { label: "正常", tone: "success" },
  degraded: { label: "降级", tone: "warning" },
  unavailable: { label: "不可用", tone: "danger" },
  unknown: { label: "未知", tone: "neutral" },
};

const CREDENTIAL_META: Record<Provider["credential_status"], { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  configured: { label: "已配置", tone: "success" },
  missing: { label: "未配置", tone: "danger" },
  invalid: { label: "无效", tone: "danger" },
  expiring: { label: "即将过期", tone: "warning" },
};

const TYPE_LABEL: Record<Provider["provider_type"], string> = {
  text: "文本",
  image: "图片",
  video: "视频",
  tts: "语音",
  multimodal: "多模态",
  presentation: "PPT",
};

const ENV_LABEL: Record<string, string> = { production: "生产", staging: "预发", development: "开发" };

function ConnectionTestButton({ providerId }: { providerId: string }) {
  const test = useTestProviderConnection();
  const [taskId, setTaskId] = useState<string | null>(null);
  const task = useTask(taskId);
  const taskStatus = task.data?.status;

  useEffect(() => {
    if (!taskId || !task.data) return;
    if (taskStatus === "completed") {
      toast({ tone: "success", title: "连接测试通过", description: task.data.progress_message ?? undefined });
      setTaskId(null);
    } else if (taskStatus === "failed") {
      toast({ tone: "danger", title: "连接测试失败", description: task.data.error?.message });
      setTaskId(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, taskStatus]);

  return (
    <Button
      size="sm"
      variant="secondary"
      loading={test.isPending || taskId !== null}
      onClick={() =>
        test.mutate(providerId, {
          onSuccess: (task) => setTaskId(task.task_id),
          onError: (error) => toast({ tone: "danger", title: "连接测试发起失败", description: error.message }),
        })
      }
    >
      <Plug className="size-3.5" aria-hidden />
      连接测试
    </Button>
  );
}

function ProviderFormDialog({
  open,
  onOpenChange,
  provider,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: Provider | null;
}) {
  const create = useCreateProvider();
  const update = useUpdateProvider();
  const [form, setForm] = useState<{
    name: string;
    provider_type: ProviderCreateBody["provider_type"];
    base_url: string;
    environment: NonNullable<ProviderCreateBody["environment"]>;
    credential_value: string;
    timeout_seconds: string;
    retry_limit: string;
  }>({
    name: provider?.name ?? "",
    provider_type: provider?.provider_type ?? "text",
    base_url: provider?.base_url ?? "",
    environment: provider?.environment ?? "production",
    credential_value: "",
    timeout_seconds: String(provider?.timeout_seconds ?? 60),
    retry_limit: String(provider?.retry_limit ?? 2),
  });
  const pending = create.isPending || update.isPending;
  const error = create.error ?? update.error;

  const submit = () => {
    const shared = {
      name: form.name.trim(),
      base_url: form.base_url.trim(),
      environment: form.environment,
      timeout_seconds: Number(form.timeout_seconds) || 60,
      retry_limit: Number(form.retry_limit) || 0,
      // 密钥只写不读：留空表示不修改
      ...(form.credential_value.trim() ? { credential_value: form.credential_value.trim() } : {}),
    };
    if (provider) {
      update.mutate(
        { providerId: provider.provider_id, patch: shared },
        {
          onSuccess: () => {
            toast({ tone: "success", title: "Provider 已更新" });
            onOpenChange(false);
          },
        },
      );
    } else {
      create.mutate(
        { ...shared, provider_type: form.provider_type, enabled: true },
        {
          onSuccess: () => {
            toast({ tone: "success", title: "Provider 已创建", description: "建议先做一次连接测试。" });
            onOpenChange(false);
          },
        },
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        title={provider ? `编辑 ${provider.name}` : "新增 Provider"}
        description="密钥提交后由后端加密保存，界面只显示掩码与配置状态，不会回显明文。"
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="名称" required>
              {({ id }) => <Input id={id} value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} />}
            </FormField>
            <FormField label="能力类型" required>
              {({ id }) => (
                <Select
                  value={form.provider_type}
                  onValueChange={(value) => setForm((prev) => ({ ...prev, provider_type: value as ProviderCreateBody["provider_type"] }))}
                >
                  <SelectTrigger id={id} disabled={provider !== null}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(TYPE_LABEL).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>
          </div>
          <FormField label="Base URL" required>
            {({ id }) => (
              <Input
                id={id}
                type="url"
                placeholder="https://api.example.com/v1"
                value={form.base_url}
                onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
              />
            )}
          </FormField>
          <FormField
            label={provider ? "更新密钥（留空则不修改）" : "API 密钥"}
            required={!provider}
            description={provider?.credential_mask ? `当前：${provider.credential_mask}` : undefined}
          >
            {({ id, describedBy }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                type="password"
                autoComplete="off"
                placeholder="sk-…"
                value={form.credential_value}
                onChange={(event) => setForm((prev) => ({ ...prev, credential_value: event.target.value }))}
              />
            )}
          </FormField>
          <div className="grid grid-cols-3 gap-3">
            <FormField label="环境">
              {({ id }) => (
                <Select
                  value={form.environment}
                  onValueChange={(value) =>
                    setForm((prev) => ({ ...prev, environment: value as NonNullable<ProviderCreateBody["environment"]> }))
                  }
                >
                  <SelectTrigger id={id}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ENV_LABEL).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </FormField>
            <FormField label="超时（秒）">
              {({ id }) => (
                <Input id={id} type="number" min={1} value={form.timeout_seconds} onChange={(event) => setForm((prev) => ({ ...prev, timeout_seconds: event.target.value }))} />
              )}
            </FormField>
            <FormField label="重试次数">
              {({ id }) => (
                <Input id={id} type="number" min={0} value={form.retry_limit} onChange={(event) => setForm((prev) => ({ ...prev, retry_limit: event.target.value }))} />
              )}
            </FormField>
          </div>
          {error ? <AppErrorPanel error={error} title="保存失败" /> : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            loading={pending}
            disabled={!form.name.trim() || !form.base_url.trim() || (!provider && !form.credential_value.trim())}
            onClick={submit}
          >
            {provider ? "保存修改" : "创建 Provider"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Provider 管理页：列表 / 新增编辑（密钥仅掩码）/ 启停 / 连接测试。 */
export function AdminProvidersPage() {
  const providers = useProviders();
  const update = useUpdateProvider();
  const [dialogFor, setDialogFor] = useState<{ open: boolean; provider: Provider | null }>({ open: false, provider: null });

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="Provider 配置"
        description="模型服务接入点管理。密钥仅显示掩码与状态，前端不可读取明文。"
        actions={
          <Button onClick={() => setDialogFor({ open: true, provider: null })}>
            <Plus className="size-4" aria-hidden />
            新增 Provider
          </Button>
        }
      />

      {providers.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-20" />
          ))}
        </div>
      ) : providers.isError ? (
        <AppErrorPanel error={providers.error} title="Provider 加载失败" onRetry={() => void providers.refetch()} />
      ) : (
        <ul className="space-y-2">
          {(providers.data ?? []).map((provider) => {
            const health = HEALTH_META[provider.health_status];
            const credential = CREDENTIAL_META[provider.credential_status];
            return (
              <li key={provider.provider_id} className="rounded-card border border-line bg-surface-1 px-4 py-3">
                <div className="flex items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-ink-1">{provider.name}</span>
                      <Badge tone="neutral">{TYPE_LABEL[provider.provider_type]}</Badge>
                      <Badge tone={health.tone}>{health.label}</Badge>
                      {provider.environment ? <span className="text-xs text-ink-muted">{ENV_LABEL[provider.environment]}</span> : null}
                    </div>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-muted">
                      <span>{provider.base_url}</span>
                      <span className="inline-flex items-center gap-1">
                        <KeyRound className="size-3" aria-hidden />
                        密钥 <Badge tone={credential.tone}>{credential.label}</Badge>
                        {provider.credential_mask ? <code className="font-mono">{provider.credential_mask}</code> : null}
                        {provider.credential_updated_at ? `（更新于 ${formatRelativeTime(provider.credential_updated_at)}）` : null}
                      </span>
                    </p>
                  </div>
                  <ConnectionTestButton providerId={provider.provider_id} />
                  <Button size="sm" variant="ghost" onClick={() => setDialogFor({ open: true, provider })}>
                    编辑
                  </Button>
                  <label className="flex items-center gap-1.5 text-xs text-ink-2">
                    <Switch
                      checked={provider.enabled}
                      onCheckedChange={(checked) =>
                        update.mutate(
                          { providerId: provider.provider_id, patch: { enabled: checked } },
                          {
                            onSuccess: () =>
                              toast({ tone: "success", title: checked ? "已启用" : "已停用", description: provider.name }),
                          },
                        )
                      }
                      aria-label={`${provider.enabled ? "停用" : "启用"} ${provider.name}`}
                    />
                    {provider.enabled ? "启用中" : "已停用"}
                  </label>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <p className="flex items-center gap-1.5 text-xs text-ink-muted">
        <ShieldCheck className="size-3.5" aria-hidden />
        所有模型调用均由后端网关代理执行；前端从不直连模型服务，也不存储任何密钥。
      </p>

      {dialogFor.open ? (
        <ProviderFormDialog
          key={dialogFor.provider?.provider_id ?? "new"}
          open={dialogFor.open}
          onOpenChange={(open) => setDialogFor((prev) => ({ ...prev, open }))}
          provider={dialogFor.provider}
        />
      ) : null}
    </div>
  );
}
