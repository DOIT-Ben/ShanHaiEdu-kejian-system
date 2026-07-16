import { useEffect, useState } from "react";
import { useBudgets, useSaveBudgets } from "@/features/admin";
import { AppError } from "@/shared/api";
import { formatMinorUnits } from "@/shared/lib/format";
import {
  Button,
  FormField,
  Input,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Progress,
  RadioGroup,
  RadioGroupItem,
  Skeleton,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, ConflictDialog } from "@/widgets";

interface BudgetForm {
  platform_daily: string;
  teacher_quota: string;
  project_default: string;
  node_run_max: string;
  overage_policy: "pause" | "require_authorization";
}

/** 预算与配额页：平台/教师/项目/单次上限 + 超额策略（乐观锁）。 */
export function AdminBudgetsPage() {
  const budgets = useBudgets();
  const save = useSaveBudgets();
  const [form, setForm] = useState<BudgetForm | null>(null);
  const [conflictOpen, setConflictOpen] = useState(false);

  useEffect(() => {
    if (budgets.data) {
      setForm({
        platform_daily: String(budgets.data.platform_daily_minor_units / 100),
        teacher_quota: String(budgets.data.teacher_quota_minor_units / 100),
        project_default: String(budgets.data.project_default_minor_units / 100),
        node_run_max: String(budgets.data.node_run_max_minor_units / 100),
        overage_policy: budgets.data.overage_policy,
      });
    }
  }, [budgets.data]);

  const doSave = (rowVersion: number) => {
    if (!form) return;
    save.mutate(
      {
        platform_daily_minor_units: Math.round(Number(form.platform_daily) * 100) || 0,
        teacher_quota_minor_units: Math.round(Number(form.teacher_quota) * 100) || 0,
        project_default_minor_units: Math.round(Number(form.project_default) * 100) || 0,
        node_run_max_minor_units: Math.round(Number(form.node_run_max) * 100) || 0,
        overage_policy: form.overage_policy,
        row_version: rowVersion,
      },
      {
        onSuccess: () => toast({ tone: "success", title: "预算配置已保存" }),
        onError: (error) => {
          if (error instanceof AppError && error.status === 409) setConflictOpen(true);
        },
      },
    );
  };

  if (budgets.isPending || !form) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-80" />
      </div>
    );
  }
  if (budgets.isError) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <AppErrorPanel error={budgets.error} title="预算配置加载失败" onRetry={() => void budgets.refetch()} />
      </div>
    );
  }

  const data = budgets.data;
  const dailySpentPercent =
    data.platform_daily_minor_units > 0 ? Math.min(100, ((data.platform_daily_spent_minor_units ?? 0) / data.platform_daily_minor_units) * 100) : 0;

  return (
    <div className="max-w-3xl space-y-4 p-6">
      <PageHeader title="预算与配额" description="控制平台与个人的模型调用费用；超出配额的付费生成需要单独授权。" />

      <Panel>
        <PanelHeader title="今日平台用量" />
        <PanelBody>
          <div className="flex items-center justify-between text-sm">
            <span className="text-ink-2">
              已用 {formatMinorUnits(data.platform_daily_spent_minor_units ?? 0)} / {formatMinorUnits(data.platform_daily_minor_units)}
            </span>
            <span className="tabular-nums text-ink-muted">{Math.round(dailySpentPercent)}%</span>
          </div>
          <Progress className="mt-2" value={dailySpentPercent} />
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="额度配置" description="单位：元。" />
        <PanelBody className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <FormField label="平台每日上限">
              {({ id }) => (
                <Input id={id} type="number" min={0} value={form.platform_daily} onChange={(event) => setForm((prev) => (prev ? { ...prev, platform_daily: event.target.value } : prev))} />
              )}
            </FormField>
            <FormField label="教师月度配额">
              {({ id }) => (
                <Input id={id} type="number" min={0} value={form.teacher_quota} onChange={(event) => setForm((prev) => (prev ? { ...prev, teacher_quota: event.target.value } : prev))} />
              )}
            </FormField>
            <FormField label="项目默认预算">
              {({ id }) => (
                <Input id={id} type="number" min={0} value={form.project_default} onChange={(event) => setForm((prev) => (prev ? { ...prev, project_default: event.target.value } : prev))} />
              )}
            </FormField>
            <FormField label="单次生成上限">
              {({ id }) => (
                <Input id={id} type="number" min={0} value={form.node_run_max} onChange={(event) => setForm((prev) => (prev ? { ...prev, node_run_max: event.target.value } : prev))} />
              )}
            </FormField>
          </div>
          <FormField label="超额策略">
            {() => (
              <RadioGroup
                value={form.overage_policy}
                onValueChange={(value) => setForm((prev) => (prev ? { ...prev, overage_policy: value as BudgetForm["overage_policy"] } : prev))}
                className="space-y-2"
              >
                <label className="flex items-center gap-2 text-sm text-ink-1">
                  <RadioGroupItem value="require_authorization" />
                  需授权后继续（推荐）：超出额度的付费生成需教师逐次确认费用
                </label>
                <label className="flex items-center gap-2 text-sm text-ink-1">
                  <RadioGroupItem value="pause" />
                  直接暂停：超出额度后暂停全部付费生成，直到调高额度
                </label>
              </RadioGroup>
            )}
          </FormField>
          {(data.organization_budgets ?? []).length > 0 ? (
            <div>
              <p className="mb-1.5 text-xs font-semibold text-ink-muted">组织月度预算</p>
              <ul className="space-y-1.5">
                {(data.organization_budgets ?? []).map((org) => (
                  <li key={org.organization_id} className="flex items-center gap-3 rounded-control border border-line px-3 py-2 text-sm">
                    <span className="min-w-0 flex-1 truncate text-ink-1">{org.organization_name}</span>
                    <span className="text-xs text-ink-muted">
                      已用 {formatMinorUnits(org.spent_minor_units)} / {formatMinorUnits(org.monthly_limit_minor_units)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {save.isError && !(save.error instanceof AppError && save.error.status === 409) ? (
            <AppErrorPanel error={save.error} title="保存失败" />
          ) : null}
          <div className="flex justify-end">
            <Button onClick={() => doSave(data.row_version)} loading={save.isPending}>
              保存配置
            </Button>
          </div>
        </PanelBody>
      </Panel>

      <ConflictDialog
        open={conflictOpen}
        onOpenChange={setConflictOpen}
        serverRowVersion={
          save.error instanceof AppError
            ? ((save.error.details as { server_row_version?: number } | undefined)?.server_row_version ?? null)
            : null
        }
        onKeepMine={() => {
          setConflictOpen(false);
          const serverRowVersion =
            save.error instanceof AppError
              ? (save.error.details as { server_row_version?: number } | undefined)?.server_row_version
              : undefined;
          doSave(serverRowVersion ?? data.row_version);
        }}
        onUseServer={() => {
          setConflictOpen(false);
          void budgets.refetch();
        }}
      />
    </div>
  );
}
