import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate, useSearchParams } from "react-router";
import { GraduationCap } from "lucide-react";
import { useLogin } from "@/features/session";
import { AppError } from "@/shared/api";
import { Button, FormField, Input } from "@/shared/ui";

const loginSchema = z.object({
  identifier: z.string().min(1, "请输入邮箱或工号"),
  password: z.string().min(1, "请输入密码"),
});

type LoginForm = z.infer<typeof loginSchema>;

export function LoginPage() {
  const login = useLogin();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifier: "", password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      const redirect = searchParams.get("redirect");
      await navigate(redirect && redirect.startsWith("/") ? redirect : "/app", { replace: true });
    } catch {
      // 错误在下方面板展示
    }
  });

  const error = login.error instanceof AppError ? login.error : null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="mx-auto flex size-12 items-center justify-center rounded-card bg-brand text-white">
            <GraduationCap className="size-6" aria-hidden />
          </span>
          <h1 className="mt-4 text-xl font-semibold text-ink-1">山海教育课件系统</h1>
          <p className="mt-1 text-sm text-ink-2">面向小学数学的课件创作工作室</p>
        </div>
        <form
          className="space-y-4 rounded-panel border border-line bg-surface-1 p-6"
          onSubmit={(event) => void onSubmit(event)}
          noValidate
        >
          <FormField label="邮箱或工号" required error={form.formState.errors.identifier?.message}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                type="email"
                autoComplete="username"
                placeholder="name@school.edu"
                {...form.register("identifier")}
              />
            )}
          </FormField>
          <FormField label="密码" required error={form.formState.errors.password?.message}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                aria-describedby={describedBy}
                type="password"
                autoComplete="current-password"
                placeholder="请输入密码"
                {...form.register("password")}
              />
            )}
          </FormField>
          {error ? (
            <p role="alert" className="rounded-control bg-danger-surface px-3 py-2 text-sm text-danger">
              {error.message}
            </p>
          ) : null}
          <Button type="submit" className="w-full" loading={login.isPending}>
            登录
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-ink-muted">登录状态由学校统一账号体系管理，遇到问题请联系管理员。</p>
      </div>
    </div>
  );
}
