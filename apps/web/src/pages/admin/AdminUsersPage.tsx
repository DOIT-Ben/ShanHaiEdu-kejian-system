import * as Dialog from "@radix-ui/react-dialog";
import { Plus, Search, ShieldCheck, UserRound, X } from "lucide-react";
import { useMemo, useState } from "react";
import { getMockDraft, saveMockDraft } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { HorizontalScrollArea } from "@/shared/ui/HorizontalScrollArea";
import { IconButton } from "@/shared/ui/IconButton";
import { Select } from "@/shared/ui/Select";

const USERS_DRAFT_KEY = "admin.users";

type UserRecord = {
  name: string;
  account: string;
  role: string;
  scope: string;
  status: string;
};

const defaultUsers: UserRecord[] = [
  {
    name: "林若晴",
    account: "lin.ruoqing@example.edu",
    role: "教师",
    scope: "小学数学组",
    status: "正常",
  },
  {
    name: "周晓舟",
    account: "zhou.xiaozhou@example.edu",
    role: "内容管理员",
    scope: "内容中心",
    status: "正常",
  },
  {
    name: "陈明远",
    account: "chen.mingyuan@example.edu",
    role: "模型管理员",
    scope: "模型服务",
    status: "正常",
  },
  {
    name: "王思文",
    account: "wang.siwen@example.edu",
    role: "教师",
    scope: "小学数学组",
    status: "已停用",
  },
];

function readUsers() {
  return getMockDraft<UserRecord[]>(USERS_DRAFT_KEY)?.value ?? defaultUsers;
}

const emptyMember = {
  account: "",
  name: "",
  role: "教师",
  scope: "小学数学组",
};

export function AdminUsersPage() {
  const [users, setUsers] = useState(readUsers);
  const [query, setQuery] = useState("");
  const [selectedAccount, setSelectedAccount] = useState<string | null>(null);
  const [permission, setPermission] = useState({ role: "教师", scope: "小学数学组" });
  const [message, setMessage] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState("");
  const [newMember, setNewMember] = useState(emptyMember);
  const visibleUsers = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return keyword
      ? users.filter(
          (user) =>
            user.name.toLowerCase().includes(keyword) ||
            user.account.toLowerCase().includes(keyword),
        )
      : users;
  }, [query, users]);
  const selectedUser = users.find((user) => user.account === selectedAccount);
  const saveUsers = (next: UserRecord[]) => {
    saveMockDraft(USERS_DRAFT_KEY, next);
    setUsers(next);
  };
  const changeCreateOpen = (open: boolean) => {
    setCreateOpen(open);
    if (!open) {
      setCreateError("");
      setNewMember(emptyMember);
    }
  };
  const addMember = () => {
    const name = newMember.name.trim();
    const account = newMember.account.trim().toLowerCase();
    if (!name || !account || !newMember.role || !newMember.scope) {
      setCreateError("请完整填写姓名、账号、角色和权限范围");
      return;
    }
    if (users.some((user) => user.account.toLowerCase() === account)) {
      setCreateError("该账号已经存在，请检查后重试");
      return;
    }
    const member: UserRecord = {
      account,
      name,
      role: newMember.role,
      scope: newMember.scope,
      status: "正常",
    };
    saveUsers([...users, member]);
    setQuery("");
    setMessage(`${member.name}已加入`);
    changeCreateOpen(false);
  };
  const openPermission = (user: UserRecord) => {
    setSelectedAccount(user.account);
    setPermission({ role: user.role, scope: user.scope });
    setMessage(`正在编辑${user.name}的权限`);
  };
  return (
    <Dialog.Root onOpenChange={changeCreateOpen} open={createOpen}>
      <div className="p-5 md:p-6">
        <FocusPageHeader
          action={
            <Dialog.Trigger asChild>
              <Button>
                <Plus aria-hidden="true" />
                添加成员
              </Button>
            </Dialog.Trigger>
          }
          description="按角色和资源范围授予权限；普通教师不会看到无权限的管理入口。"
          title="用户权限"
        />
        <div className="mt-7 flex max-w-md items-center gap-2 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3">
          <Search aria-hidden="true" className="size-4 text-[var(--sh-ink-faint)]" />
          <input
            aria-label="搜索成员"
            className="min-h-11 min-w-0 flex-1 outline-none"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索姓名或账号"
            value={query}
          />
        </div>
        <HorizontalScrollArea
          ariaLabel="成员权限列表"
          className="mt-5"
          hintTestId="admin-users-table-scroll-next"
          viewportClassName="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
        >
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-[var(--sh-surface-soft)] text-xs text-[var(--sh-ink-muted)]">
              <tr>
                <th className="px-5 py-3">成员</th>
                <th className="px-5 py-3">角色</th>
                <th className="px-5 py-3">权限范围</th>
                <th className="px-5 py-3">状态</th>
                <th className="px-5 py-3">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--sh-line-subtle)]">
              {visibleUsers.map((user) => (
                <tr key={user.account}>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                        <UserRound aria-hidden="true" className="size-4" />
                      </span>
                      <div>
                        <p className="font-semibold text-[var(--sh-ink-strong)]">{user.name}</p>
                        <p className="text-xs text-[var(--sh-ink-muted)]">{user.account}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className="inline-flex items-center gap-1.5">
                      <ShieldCheck
                        aria-hidden="true"
                        className="size-4 text-[var(--sh-brand-600)]"
                      />
                      {user.role}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-[var(--sh-ink-muted)]">{user.scope}</td>
                  <td
                    className={`px-5 py-4 font-semibold ${user.status === "正常" ? "text-[var(--sh-success)]" : "text-[var(--sh-ink-faint)]"}`}
                  >
                    {user.status}
                  </td>
                  <td className="px-5 py-4">
                    <button
                      aria-label={`编辑${user.name}的权限`}
                      className="font-semibold text-[var(--sh-brand-600)]"
                      onClick={() => openPermission(user)}
                      type="button"
                    >
                      编辑权限
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </HorizontalScrollArea>
        {visibleUsers.length === 0 ? (
          <p className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 text-sm text-[var(--sh-ink-muted)]">
            没有找到匹配成员。
          </p>
        ) : null}
        {selectedUser ? (
          <section className="mt-5 rounded-[var(--sh-radius-md)] border border-[var(--sh-brand-100)] bg-[var(--sh-surface-elevated)] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold text-[var(--sh-brand-600)]">
                  {selectedUser.name}
                </p>
                <h2 className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)]">编辑成员权限</h2>
              </div>
              <Button onClick={() => setSelectedAccount(null)} size="sm" variant="quiet">
                关闭
              </Button>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                角色
                <Select
                  ariaLabel="角色"
                  className="mt-2 w-full font-normal"
                  onValueChange={(role) => setPermission({ ...permission, role })}
                  options={["教师", "内容管理员", "模型管理员"].map((role) => ({
                    label: role,
                    value: role,
                  }))}
                  value={permission.role}
                />
              </label>
              <label className="text-sm font-semibold">
                权限范围
                <Select
                  ariaLabel="权限范围"
                  className="mt-2 w-full font-normal"
                  onValueChange={(scope) => setPermission({ ...permission, scope })}
                  options={["小学数学组", "内容中心", "模型服务", "全部项目"].map((scope) => ({
                    label: scope,
                    value: scope,
                  }))}
                  value={permission.scope}
                />
              </label>
            </div>
            <Button
              className="mt-4"
              onClick={() => {
                const next = users.map((user) =>
                  user.account === selectedUser.account ? { ...user, ...permission } : user,
                );
                saveUsers(next);
                setMessage(`${selectedUser.name}的权限已保存`);
              }}
              size="sm"
            >
              保存权限
            </Button>
          </section>
        ) : null}
        {message ? (
          <p aria-live="polite" className="mt-3 text-sm font-semibold text-[var(--sh-brand-700)]">
            {message}
          </p>
        ) : null}
      </div>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)] backdrop-blur-[1px]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[min(92vw,560px)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <Dialog.Title className="text-xl font-bold text-[var(--sh-ink-strong)]">
                添加成员
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                填写成员账号并确定可以使用的管理范围。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton label="关闭添加成员">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              addMember();
            }}
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                姓名
                <input
                  className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 font-normal outline-none focus:border-[var(--sh-brand-500)]"
                  onChange={(event) =>
                    setNewMember((current) => ({ ...current, name: event.target.value }))
                  }
                  required
                  value={newMember.name}
                />
              </label>
              <label className="text-sm font-semibold">
                账号
                <input
                  className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 font-normal outline-none focus:border-[var(--sh-brand-500)]"
                  onChange={(event) =>
                    setNewMember((current) => ({ ...current, account: event.target.value }))
                  }
                  placeholder="name@example.edu"
                  required
                  type="email"
                  value={newMember.account}
                />
              </label>
              <label className="text-sm font-semibold">
                角色
                <Select
                  ariaLabel="角色"
                  className="mt-2 w-full font-normal"
                  onValueChange={(role) => setNewMember((current) => ({ ...current, role }))}
                  options={["教师", "内容管理员", "模型管理员"].map((role) => ({
                    label: role,
                    value: role,
                  }))}
                  value={newMember.role}
                />
              </label>
              <label className="text-sm font-semibold">
                权限范围
                <Select
                  ariaLabel="权限范围"
                  className="mt-2 w-full font-normal"
                  onValueChange={(scope) => setNewMember((current) => ({ ...current, scope }))}
                  options={["小学数学组", "内容中心", "模型服务", "全部项目"].map((scope) => ({
                    label: scope,
                    value: scope,
                  }))}
                  value={newMember.scope}
                />
              </label>
            </div>
            {createError ? (
              <p className="text-sm font-semibold text-[var(--sh-danger)]" role="alert">
                {createError}
              </p>
            ) : null}
            <div className="flex justify-end gap-2 pt-2">
              <Dialog.Close asChild>
                <Button type="button" variant="quiet">
                  取消
                </Button>
              </Dialog.Close>
              <Button
                disabled={
                  !newMember.name.trim() ||
                  !newMember.account.trim() ||
                  !newMember.role ||
                  !newMember.scope
                }
                type="submit"
              >
                确认添加
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
