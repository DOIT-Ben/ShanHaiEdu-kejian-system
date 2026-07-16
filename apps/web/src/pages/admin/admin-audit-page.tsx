import { useState } from "react";
import { ScrollText, Search } from "lucide-react";
import { useAuditLog } from "@/features/admin";
import { formatDateTime } from "@/shared/lib/format";
import { EmptyState, Input, PageHeader, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Skeleton } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const OBJECT_TYPES = [
  { value: "provider", label: "Provider" },
  { value: "model", label: "模型" },
  { value: "route_policy", label: "路由策略" },
  { value: "budget", label: "预算" },
  { value: "template", label: "Prompt 模板" },
  { value: "user", label: "用户" },
  { value: "project", label: "项目" },
];

/** 审计日志页：管理操作留痕（只读）。 */
export function AdminAuditPage() {
  const [filters, setFilters] = useState<{ object_type?: string; keyword?: string }>({});
  const [keywordInput, setKeywordInput] = useState("");
  const audit = useAuditLog(filters);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="审计日志" description="记录全部管理操作：配置修改、发布、回滚、权限调整与费用授权。" />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <Input
            className="pl-8"
            placeholder="搜索操作人或摘要"
            value={keywordInput}
            onChange={(event) => {
              setKeywordInput(event.target.value);
              setFilters((prev) => ({ ...prev, keyword: event.target.value || undefined }));
            }}
          />
        </div>
        <Select
          value={filters.object_type ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, object_type: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-36" aria-label="按对象类型筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部对象</SelectItem>
            {OBJECT_TYPES.map((type) => (
              <SelectItem key={type.value} value={type.value}>
                {type.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {audit.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, index) => (
            <Skeleton key={index} className="h-12" />
          ))}
        </div>
      ) : audit.isError ? (
        <AppErrorPanel error={audit.error} title="审计日志加载失败" onRetry={() => void audit.refetch()} />
      ) : (audit.data ?? []).length === 0 ? (
        <EmptyState icon={<ScrollText className="size-8" aria-hidden />} title="暂无审计记录" />
      ) : (
        <ul className="divide-y divide-divider rounded-panel border border-line bg-surface-1">
          {(audit.data ?? []).map((entry) => (
            <li key={entry.audit_id} className="px-4 py-2.5">
              <div className="flex items-center gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink-1">
                    <span className="font-medium">{entry.actor_name}</span>
                    <span className="mx-1 text-ink-muted">·</span>
                    {entry.summary ?? entry.action}
                  </p>
                  <p className="text-xs text-ink-muted">
                    {entry.action} · {entry.object_type}
                    {entry.object_id ? ` #${entry.object_id}` : ""} · {formatDateTime(entry.occurred_at)}
                    {entry.trace_id ? (
                      <span className="ml-2 font-mono text-[10px] opacity-70">Trace: {entry.trace_id}</span>
                    ) : null}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
