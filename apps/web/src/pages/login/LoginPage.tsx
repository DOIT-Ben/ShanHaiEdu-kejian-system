import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router";
import { Mountain } from "lucide-react";
import { client, unwrap, qk, AppError } from "@/shared/api";
import { env } from "@/shared/config/env";
import { Button, FormField, Input } from "@/shared/ui";

/** 登录页：品牌区 + 邮箱密码；mock 模式提供演示账号一键填充。 */
export default function LoginPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const login = useMutation({
    mutationFn: async (input: { email: string; password: string }) => {
      const result = unwrap(await client.POST("/auth/login", { body: input }));
      return result.data.user;
    },
    onSuccess: (user) => {
      queryClient.setQueryData(qk.session, user);
      const returnTo = params.get("return_to");
      void navigate(returnTo && returnTo.startsWith("/") ? returnTo : "/app", { replace: true });
    },
    onError: (error) => {
      setFormError(error instanceof AppError ? error.message : "登录失败，请稍后重试。");
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);
    if (!email.trim() || !password) {
      setFormError("请输入邮箱和密码。");
      return;
    }
    login.mutate({ email: email.trim(), password });
  };

  return (
    <div className="flex min-h-screen bg-canvas">
      <aside className="sh-hero-gradient sh-mountain-texture hidden w-[46%] flex-col justify-between p-12 lg:flex">
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-md bg-brand-500 text-white">
            <Mountain className="size-5" aria-hidden />
          </span>
          <span className="text-lg font-semibold text-ink-strong">山海创作空间</span>
        </div>
        <div className="max-w-md">
          <h1 className="text-3xl font-semibold leading-snug text-ink-strong">
            把一份教材，
            <br />
            变成完整的课堂作品
          </h1>
          <p className="mt-4 text-base leading-relaxed text-ink-muted">
            上传教材，系统陪你完成教案、课堂导入、PPT 与导入视频的每一步；每一步都由你确认。
          </p>
        </div>
        <p className="text-xs text-ink-faint">山海教育 · 教师创作台</p>
      </aside>
      <main className="flex flex-1 items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <h2 className="text-xl font-semibold text-ink-strong">登录</h2>
          <p className="mt-1 text-sm text-ink-muted">使用学校分配的账号进入创作空间。</p>
          <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
            <FormField label="邮箱" required>
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  type="email"
                  autoComplete="username"
                  value={email}
                  aria-describedby={describedBy}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@school.edu"
                />
              )}
            </FormField>
            <FormField label="密码" required error={formError ?? undefined}>
              {({ id, describedBy }) => (
                <Input
                  id={id}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  aria-describedby={describedBy}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="请输入密码"
                />
              )}
            </FormField>
            <Button type="submit" className="w-full" loading={login.isPending} loadingText="正在登录…">
              登录
            </Button>
          </form>
          {env.apiMode === "mock" ? (
            <div className="mt-8 rounded-md border border-line-subtle bg-surface p-4">
              <p className="text-xs font-medium text-ink-muted">演示账号（Mock 模式）</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {[
                  { label: "教师 林晓雨", email: "teacher@shanhai.edu" },
                  { label: "内容管理员", email: "content@shanhai.edu" },
                  { label: "系统管理员", email: "admin@shanhai.edu" },
                ].map((account) => (
                  <Button
                    key={account.email}
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setEmail(account.email);
                      setPassword("demo1234");
                    }}
                  >
                    {account.label}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </main>
    </div>
  );
}
