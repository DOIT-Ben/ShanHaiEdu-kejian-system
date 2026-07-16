import { useState } from "react";
import { Search, UserCog } from "lucide-react";
import { useAdminUsers, useUpdateAdminUser } from "@/features/admin";
import type { AdminUser } from "@/shared/api/types";
import { formatRelativeTime, ROLE_LABEL } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Textarea,
  toast,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

type Role = AdminUser["role"];

function EditUserDialog({ user, onClose }: { user: AdminUser | null; onClose: () => void }) {
  const update = useUpdateAdminUser();
  const [role, setRole] = useState<Role>(user?.role ?? "teacher");
  const [status, setStatus] = useState<AdminUser["status"]>(user?.status ?? "active");
  const [reason, setReason] = useState("");

  return (
    <Dialog open={user !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent title={`调整 ${user?.display_name} 的权限`} description="角色与状态变更会记入审计日志。">
        <div className="space-y-3">
          <FormField label="角色" required>
            {({ id }) => (
              <Select value={role} onValueChange={(value) => setRole(value as Role)}>
                <SelectTrigger id={id}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(ROLE_LABEL).map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField label="账号状态" required>
            {({ id }) => (
              <Select value={status} onValueChange={(value) => setStatus(value as AdminUser["status"])}>
                <SelectTrigger id={id}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">正常</SelectItem>
                  <SelectItem value="disabled">停用</SelectItem>
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField label="变更理由" required>
            {({ id }) => <Textarea id={id} rows={2} value={reason} onChange={(event) => setReason(event.target.value)} />}
          </FormField>
          {update.isError ? <AppErrorPanel error={update.error} title="保存失败" /> : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button
            loading={update.isPending}
            disabled={!reason.trim()}
            onClick={() => {
              if (!user) return;
              update.mutate(
                { userId: user.user_id, role, status, reason: reason.trim() },
                {
                  onSuccess: () => {
                    toast({ tone: "success", title: "用户权限已更新" });
                    onClose();
                  },
                },
              );
            }}
          >
            保存变更
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 用户与权限页。 */
export function AdminUsersPage() {
  const [filters, setFilters] = useState<{ role?: Role; status?: AdminUser["status"]; keyword?: string }>({});
  const [keywordInput, setKeywordInput] = useState("");
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const users = useAdminUsers(filters);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="用户与权限" description="管理平台账号的角色与状态；账号来源为学校统一账号体系。" />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <Input
            className="pl-8"
            placeholder="搜索姓名或邮箱"
            value={keywordInput}
            onChange={(event) => {
              setKeywordInput(event.target.value);
              setFilters((prev) => ({ ...prev, keyword: event.target.value || undefined }));
            }}
          />
        </div>
        <Select
          value={filters.role ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, role: value === "all" ? undefined : (value as Role) }))}
        >
          <SelectTrigger className="w-36" aria-label="按角色筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部角色</SelectItem>
            {Object.entries(ROLE_LABEL).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filters.status ?? "all"}
          onValueChange={(value) =>
            setFilters((prev) => ({ ...prev, status: value === "all" ? undefined : (value as AdminUser["status"]) }))
          }
        >
          <SelectTrigger className="w-28" aria-label="按状态筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="active">正常</SelectItem>
            <SelectItem value="disabled">停用</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {users.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-14" />
          ))}
        </div>
      ) : users.isError ? (
        <AppErrorPanel error={users.error} title="用户加载失败" onRetry={() => void users.refetch()} />
      ) : (users.data ?? []).length === 0 ? (
        <EmptyState title="没有符合条件的用户" />
      ) : (
        <ul className="divide-y divide-divider rounded-panel border border-line bg-surface-1">
          {(users.data ?? []).map((user) => (
            <li key={user.user_id} className="flex items-center gap-3 px-4 py-3">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-selected text-sm font-semibold text-brand">
                {user.display_name.slice(0, 1)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-ink-1">{user.display_name}</p>
                <p className="text-xs text-ink-muted">
                  {user.email ?? "—"}
                  {user.organization_name ? ` · ${user.organization_name}` : ""}
                  {user.last_active_at ? ` · 最近活跃 ${formatRelativeTime(user.last_active_at)}` : ""}
                </p>
              </div>
              <Badge tone="brand">{ROLE_LABEL[user.role] ?? user.role}</Badge>
              <Badge tone={user.status === "active" ? "success" : "neutral"}>{user.status === "active" ? "正常" : "已停用"}</Badge>
              <Button size="sm" variant="ghost" onClick={() => setEditing(user)}>
                <UserCog className="size-3.5" aria-hidden />
                调整
              </Button>
            </li>
          ))}
        </ul>
      )}

      {editing ? <EditUserDialog key={editing.user_id} user={editing} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}
