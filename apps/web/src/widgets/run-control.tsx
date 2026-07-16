import { useState } from "react";
import { Play, Wallet } from "lucide-react";
import type { CostEstimate } from "@/shared/api/types";
import type { ModelProfile } from "@/features/runs";
import { formatCostRange, formatMinorUnits } from "@/shared/lib/format";
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
  Textarea,
} from "@/shared/ui";

interface ProfileOption {
  profile: string;
  business_name: string;
  description: string;
}

interface AdvancedModel {
  model_id: string;
  business_name: string;
  provider_name: string;
}

/**
 * 生成控制条：模型档位选择 → 费用预估确认 → （必要时）预算授权 → 开始生成。
 * 规则：付费生成前必须展示费用预估并确认；预算不足需先授权；
 * 不允许静默发起第二次付费任务。
 */
export function RunControl({
  profiles,
  advancedModels,
  disabled,
  disabledReason,
  runLabel = "开始生成",
  estimating,
  starting,
  onEstimate,
  onStart,
  onAuthorizeBudget,
}: {
  profiles: ProfileOption[];
  advancedModels: AdvancedModel[];
  disabled?: boolean;
  disabledReason?: string | null;
  runLabel?: string;
  estimating?: boolean;
  starting?: boolean;
  onEstimate: (input: { modelProfile: ModelProfile; modelId?: string | null }) => Promise<CostEstimate>;
  onStart: (input: { modelProfile: ModelProfile; modelId?: string | null; budgetAuthorizationId?: string | null }) => void;
  onAuthorizeBudget?: (input: { estimatedMaxMinorUnits: number; reason: string }) => Promise<{ budget_authorization_id: string }>;
}) {
  const [profile, setProfile] = useState<ModelProfile>("recommended");
  const [modelId, setModelId] = useState<string | null>(null);
  const [estimate, setEstimate] = useState<CostEstimate | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [authReason, setAuthReason] = useState("");
  const [authorizing, setAuthorizing] = useState(false);

  const isAdvanced = profile === "advanced";

  const requestRun = async () => {
    const result = await onEstimate({ modelProfile: profile, modelId: isAdvanced ? modelId : null });
    setEstimate(result);
    setConfirmOpen(true);
  };

  const confirmRun = async () => {
    if (!estimate) return;
    if (estimate.requires_authorization) {
      if (!onAuthorizeBudget) return;
      setAuthorizing(true);
      try {
        const auth = await onAuthorizeBudget({
          estimatedMaxMinorUnits: estimate.maximum_minor_units,
          reason: authReason.trim() || "教师确认超出预算继续生成",
        });
        onStart({ modelProfile: profile, modelId: isAdvanced ? modelId : null, budgetAuthorizationId: auth.budget_authorization_id });
      } finally {
        setAuthorizing(false);
      }
    } else {
      onStart({ modelProfile: profile, modelId: isAdvanced ? modelId : null, budgetAuthorizationId: null });
    }
    setConfirmOpen(false);
    setAuthReason("");
  };

  const paid = (estimate?.maximum_minor_units ?? 0) > 0;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select value={profile} onValueChange={(value) => setProfile(value as ModelProfile)}>
        <SelectTrigger className="w-36" aria-label="模型档位">
          <SelectValue placeholder="模型档位" />
        </SelectTrigger>
        <SelectContent>
          {profiles.map((option) => (
            <SelectItem key={option.profile} value={option.profile}>
              {option.business_name}
            </SelectItem>
          ))}
          {advancedModels.length > 0 ? <SelectItem value="advanced">高级：指定模型</SelectItem> : null}
        </SelectContent>
      </Select>
      {isAdvanced ? (
        <Select value={modelId ?? undefined} onValueChange={setModelId}>
          <SelectTrigger className="w-48" aria-label="指定模型">
            <SelectValue placeholder="选择模型" />
          </SelectTrigger>
          <SelectContent>
            {advancedModels.map((model) => (
              <SelectItem key={model.model_id} value={model.model_id}>
                {model.business_name}（{model.provider_name}）
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ) : null}
      <Button
        size="sm"
        onClick={() => void requestRun()}
        loading={estimating || starting}
        disabled={disabled || (isAdvanced && !modelId)}
        title={disabled ? (disabledReason ?? undefined) : undefined}
      >
        <Play className="size-4" aria-hidden />
        {runLabel}
      </Button>
      {disabled && disabledReason ? <span className="text-xs text-ink-muted">{disabledReason}</span> : null}

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent
          title={paid ? "确认生成费用" : "确认开始生成"}
          description={paid ? "本次生成会调用付费模型服务，确认后开始执行。" : "本步骤不产生模型费用。"}
        >
          {estimate ? (
            <div className="space-y-2 rounded-control bg-surface-2 px-4 py-3 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-2">执行模型</span>
                <span className="text-ink-1">
                  {estimate.business_model_name}
                  {estimate.provider_name ? `（${estimate.provider_name}）` : ""}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-2">预计费用</span>
                <span className="font-medium text-ink-1">
                  {formatCostRange(estimate.minimum_minor_units, estimate.maximum_minor_units, estimate.currency)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-2">生成候选数</span>
                <span className="text-ink-1">{estimate.candidate_count} 个</span>
              </div>
              {estimate.allow_fallback ? (
                <p className="text-xs text-ink-muted">主服务不可用时可能切换备用服务（切换前会再次确认费用）。</p>
              ) : null}
            </div>
          ) : null}
          {estimate?.requires_authorization ? (
            <div className="mt-3 space-y-3 rounded-control border border-warning/40 bg-warning-surface px-4 py-3">
              <p className="flex items-start gap-2 text-sm text-ink-1">
                <Wallet className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                {(estimate.parameter_summary?.authorization_reason as string | undefined) ??
                  `预计费用上限 ${formatMinorUnits(estimate.maximum_minor_units)} 超过项目剩余预算，需要额外授权。`}
              </p>
              <FormField label="授权说明">
                {({ id, describedBy }) => (
                  <Textarea
                    id={id}
                    aria-describedby={describedBy}
                    rows={2}
                    value={authReason}
                    onChange={(event) => setAuthReason(event.target.value)}
                    placeholder="说明本次超预算生成的原因（进入审计记录）。"
                  />
                )}
              </FormField>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              取消
            </Button>
            <Button onClick={() => void confirmRun()} loading={authorizing || starting}>
              {estimate?.requires_authorization ? "授权并开始生成" : paid ? "确认费用并生成" : "开始生成"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
