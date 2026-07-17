import { useAdminUsers } from "@/features/admin";
import { ROLE_LABEL } from "@/shared/lib/format";
import { formatRelativeTime } from "@/shared/lib/format";
import { Badge, PageHeader, Panel, PanelBody, Skeleton } from "@/shared/ui";

/** 用户权限（04 §2.6）：角色与状态一览（教师/内容管理员/模型管理员/系统管理员）。 */
export default function AdminUsersPage() {
  const { data: users, isPending } = useAdminUsers();

  return (
    <div>
      <PageHeader title="用户权限" description="按角色控制可见范围：教师看不到管理端，管理员按职责分区。" />
      <Panel className="mt-6">
        <PanelBody className="p-0">
          {isPending ? (
            <div className="space-y-3 p-5">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 rounded-lg" />
              ))}
            </div>
          ) : (
            <ul className="divide-y divide-line-subtle">
              {(users ?? []).map((user) => (
                <li key={user.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-600">
                    {user.name.slice(0, 1)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-ink-strong">{user.name}</span>
                    <span className="mt-0.5 block truncate text-xs text-ink-muted">{user.email}</span>
                  </span>
                  <span className="flex flex-wrap gap-1.5">
                    {user.roles.map((role) => (
                      <Badge key={role} tone={role === "teacher" ? "neutral" : "brand"}>
                        {ROLE_LABEL[role] ?? role}
                      </Badge>
                    ))}
                  </span>
                  <Badge tone={user.status === "active" ? "success" : "neutral"}>
                    {user.status === "active" ? "使用中" : "已停用"}
                  </Badge>
                  <span className="w-24 text-right text-xs text-ink-faint">
                    {user.last_active_at ? formatRelativeTime(user.last_active_at) : "—"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </PanelBody>
      </Panel>
    </div>
  );
}
