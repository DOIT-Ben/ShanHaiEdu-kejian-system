import { useState } from "react";
import { KeyRound, PlugZap, ShieldCheck } from "lucide-react";
import {
  useModelCatalog,
  useModelServiceOverview,
  useProviders,
  useTestProvider,
  useUpdateProvider,
} from "@/features/admin";
import type { Provider } from "@/shared/api";
import { formatDateTime, formatMinorUnits, formatPercent } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  FormField,
  Input,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Skeleton,
  Switch,
  toast,
} from "@/shared/ui";

const CAPABILITY_LABELS: Record<string, string> = {
  text: "文本",
  image: "图片",
  video: "视频",
  tts: "语音",
  layout: "版式",
};

const SECRET_STATUS_META: Record<string, { label: string; tone: "success" | "danger" | "warning" }> = {
  configured: { label: "已配置", tone: "success" },
  missing: { label: "未配置", tone: "danger" },
  expiring: { label: "即将过期", tone: "warning" },
};

/**
 * 模型服务（04 §2.4）：密钥只显示配置状态和尾号，绝不展示明文；
 * 输入新密钥 = 只写替换。
 */
export default function AdminModelsPage() {
  const { data: overview } = useModelServiceOverview();
  const { data: providers, isPending } = useProviders();
  const { data: models } = useModelCatalog();
  const test = useTestProvider();
  const [editing, setEditing] = useState<Provider | null>(null);

  return (
    <div>
      <PageHeader title="模型服务" description="模型供应商与密钥管理。密钥只显示状态和尾号，任何界面不显示明文。" />

      {overview ? (
        <div className="mt-6 grid gap-4 md:grid-cols-4">
          <StatCard label="今天调用" value={`${overview.today.run_count} 次`} />
          <StatCard label="成功率" value={formatPercent(overview.today.success_rate_percent)} />
          <StatCard label="今天费用" value={formatMinorUnits(overview.today.cost_minor_units)} />
          <StatCard
            label="排队任务"
            value={`${overview.backlog_count} 个`}
            warn={overview.backlog_count > 10}
          />
        </div>
      ) : null}

      {overview?.degraded && overview.degraded.length > 0 ? (
        <div className="mt-4 space-y-2">
          {overview.degraded.map((item) => (
            <p
              key={item.provider_id}
              className="rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-ink"
              role="alert"
            >
              {item.provider_name}：{item.reason}
            </p>
          ))}
        </div>
      ) : null}

      <Panel className="mt-6">
        <PanelHeader title="供应商与密钥" />
        <PanelBody className="p-0">
          {isPending ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-14 rounded-lg" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-line-subtle">
              {(providers ?? []).map((provider) => {
                const secretMeta = SECRET_STATUS_META[provider.secret_status] ?? {
                  label: provider.secret_status,
                  tone: "warning" as const,
                };
                return (
                  <li key={provider.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                    <div className="min-w-0 flex-1">
                      <p className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-strong">
                        {provider.display_name}
                        {!provider.enabled ? <Badge tone="neutral">已停用</Badge> : null}
                      </p>
                      <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                        <span>{provider.capabilities.map((c) => CAPABILITY_LABELS[c] ?? c).join(" / ")}</span>
                        <span className="flex items-center gap-1">
                          <KeyRound className="size-3.5" aria-hidden />
                          密钥{secretMeta.label}
                          {provider.secret_tail ? `（尾号 ${provider.secret_tail}）` : ""}
                        </span>
                        {provider.last_test ? (
                          <span>
                            连接测试：{provider.last_test.status === "passed" ? "通过" : "失败"}
                            {provider.last_test.tested_at ? ` · ${formatDateTime(provider.last_test.tested_at)}` : ""}
                          </span>
                        ) : null}
                      </p>
                    </div>
                    <Badge tone={secretMeta.tone}>{secretMeta.label}</Badge>
                    <span className="flex shrink-0 gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        loading={test.isPending}
                        onClick={() =>
                          test.mutate(provider.id, {
                            onSuccess: () => toast({ tone: "info", title: "连接测试已开始" }),
                            onError: (error) => toast({ tone: "danger", title: "无法测试", description: error.message }),
                          })
                        }
                      >
                        <PlugZap className="size-4" aria-hidden />
                        测试连接
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => setEditing(provider)}>
                        配置
                      </Button>
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </PanelBody>
      </Panel>

      {overview?.capability_primaries && overview.capability_primaries.length > 0 ? (
        <Panel className="mt-6">
          <PanelHeader title="各能力当前使用的模型" />
          <PanelBody className="p-0">
            <ul className="divide-y divide-line-subtle">
              {overview.capability_primaries.map((entry) => (
                <li key={entry.capability} className="flex flex-wrap items-center gap-3 px-5 py-3.5 text-sm">
                  <span className="w-14 shrink-0 font-medium text-ink-strong">
                    {CAPABILITY_LABELS[entry.capability] ?? entry.capability}
                  </span>
                  <span className="text-ink">
                    {entry.provider_name} · {entry.model_name}
                  </span>
                  {entry.fallback_provider_name ? (
                    <span className="text-xs text-ink-muted">备用：{entry.fallback_provider_name}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          </PanelBody>
        </Panel>
      ) : null}

      {models && models.length > 0 ? (
        <Panel className="mt-6">
          <PanelHeader title="模型目录" />
          <PanelBody className="p-0">
            <ul className="divide-y divide-line-subtle">
              {models.map((model) => (
                <li key={model.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                  <span className="min-w-0 flex-1 truncate text-ink">
                    {model.provider_name} · {model.model_name}
                  </span>
                  <span className="text-xs text-ink-muted">{CAPABILITY_LABELS[model.capability] ?? model.capability}</span>
                  {model.unit_cost_label ? <span className="text-xs text-ink-faint">{model.unit_cost_label}</span> : null}
                  {model.role === "primary" ? (
                    <Badge tone="brand">主用</Badge>
                  ) : model.role === "fallback" ? (
                    <Badge tone="neutral">备用</Badge>
                  ) : (
                    <Badge tone="neutral">停用</Badge>
                  )}
                </li>
              ))}
            </ul>
          </PanelBody>
        </Panel>
      ) : null}

      <ProviderDialog provider={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

function StatCard({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="rounded-lg border border-line-subtle bg-surface p-4 shadow-card">
      <p className="text-xs text-ink-muted">{label}</p>
      <p className={`mt-1 text-xl font-semibold ${warn ? "text-warning" : "text-ink-strong"}`}>{value}</p>
    </div>
  );
}

function ProviderDialog({ provider, onClose }: { provider: Provider | null; onClose: () => void }) {
  const update = useUpdateProvider();
  const [displayName, setDisplayName] = useState<string | null>(null);
  const [baseUrl, setBaseUrl] = useState<string | null>(null);
  const [secret, setSecret] = useState("");
  const [enabled, setEnabled] = useState<boolean | null>(null);

  const reset = () => {
    setDisplayName(null);
    setBaseUrl(null);
    setSecret("");
    setEnabled(null);
  };

  const save = () => {
    if (!provider) return;
    const patch: { display_name?: string; base_url?: string; secret?: string; enabled?: boolean } = {};
    if (displayName !== null && displayName !== provider.display_name) patch.display_name = displayName;
    if (baseUrl !== null && baseUrl !== (provider.base_url ?? "")) patch.base_url = baseUrl;
    if (secret.trim()) patch.secret = secret.trim();
    if (enabled !== null && enabled !== provider.enabled) patch.enabled = enabled;
    if (Object.keys(patch).length === 0) {
      onClose();
      return;
    }
    update.mutate(
      // 列表资源无单项 GET，If-Match 使用 *（匹配当前版本）
      { providerId: provider.id, etag: "*", patch },
      {
        onSuccess: () => {
          reset();
          onClose();
          toast({
            tone: "success",
            title: "配置已保存",
            description: patch.secret ? "新密钥已生效，仅保存状态与尾号。" : undefined,
          });
        },
        onError: (error) => toast({ tone: "danger", title: "保存失败", description: error.message }),
      },
    );
  };

  return (
    <Dialog open={Boolean(provider)} onOpenChange={(open) => !open && (reset(), onClose())}>
      <DialogContent
        title={`配置「${provider?.display_name ?? ""}」`}
        description="密钥为只写字段：这里输入的内容保存后不会再显示。"
      >
        <div className="space-y-4">
          <FormField label="显示名称">
            {({ id }) => (
              <Input
                id={id}
                value={displayName ?? provider?.display_name ?? ""}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            )}
          </FormField>
          <FormField label="服务地址">
            {({ id }) => (
              <Input
                id={id}
                value={baseUrl ?? provider?.base_url ?? ""}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://…"
              />
            )}
          </FormField>
          <FormField
            label="替换密钥"
            description={
              provider?.secret_tail
                ? `当前：已配置（尾号 ${provider.secret_tail}）。留空表示不更换。`
                : "当前：未配置。"
            }
          >
            {({ id }) => (
              <Input
                id={id}
                type="password"
                autoComplete="new-password"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder="输入新密钥（至少 8 位）"
              />
            )}
          </FormField>
          <div className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-soft px-3.5 py-3">
            <span className="flex items-center gap-2 text-sm text-ink">
              <ShieldCheck className="size-4 text-ink-muted" aria-hidden />
              启用该供应商
            </span>
            <Switch
              checked={enabled ?? provider?.enabled ?? false}
              onCheckedChange={(next) => setEnabled(next)}
              aria-label="启用该供应商"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => (reset(), onClose())}>
            取消
          </Button>
          <Button
            loading={update.isPending}
            loadingText="正在保存…"
            disabled={secret.trim().length > 0 && secret.trim().length < 8}
            onClick={save}
          >
            保存配置
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
