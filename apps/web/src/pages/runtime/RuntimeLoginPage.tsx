import { KeyRound, LogIn, RotateCw } from "lucide-react";
import { useState, type SubmitEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useSession } from "@/features/session/SessionProvider";
import { LoginBrandLockup, LoginVisualPanel } from "@/pages/auth/LoginBrandVisual";
import { ApiError } from "@/shared/api/client";
import { ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import { Button } from "@/shared/ui/Button";

function loginErrorMessage(reason: unknown) {
  if (!(reason instanceof ApiError)) return "登录失败，请稍后再试";
  if (reason.code === "AUTHENTICATION_FAILED") return "访问码无效，请重新输入";
  if (reason.code === "LOGIN_RATE_LIMITED") return "尝试次数过多，请稍后再试";
  if (reason.code === "ORIGIN_FORBIDDEN") return "当前页面来源未获授权";
  return "登录服务暂时不可用，请稍后再试";
}

function returnPath(state: unknown) {
  if (!state || typeof state !== "object") return "/app/projects";
  const from = (state as { from?: unknown }).from;
  return typeof from === "string" && from.startsWith("/app") ? from : "/app/projects";
}

export function RuntimeLoginPage() {
  const { login, refresh, status } = useSession();
  const location = useLocation();
  const navigate = useNavigate();
  const [accessCode, setAccessCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (status === "authenticated") {
    return <Navigate replace to={returnPath(location.state)} />;
  }

  const handleSubmit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault();
    const credential = accessCode.trim();
    if (!credential) {
      setError("请输入访问码");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await login(credential);
      await navigate(returnPath(location.state), { replace: true });
    } catch (reason) {
      setError(loginErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative grid min-h-screen bg-[var(--sh-surface-canvas)] lg:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
      <div className="absolute right-4 top-4 z-20 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/88 shadow-[var(--sh-shadow-card)] backdrop-blur-sm lg:right-6 lg:top-6">
        <ThemeSwitcher showLabel />
      </div>
      <LoginVisualPanel />
      <main className="flex items-center justify-center px-4 py-20 sm:px-6 lg:py-24">
        <section className="w-full max-w-[440px] rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)] sm:p-8">
          <LoginBrandLockup />
          <h1 className="mt-7 text-2xl font-semibold text-[var(--sh-ink-strong)]">进入山海教育</h1>
          <form className="mt-7" onSubmit={(event) => void handleSubmit(event)}>
            <label
              className="text-sm font-medium text-[var(--sh-ink-default)]"
              htmlFor="access-code"
            >
              学校访问码
            </label>
            <div className="relative mt-2">
              <KeyRound
                aria-hidden="true"
                className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[var(--sh-ink-faint)]"
              />
              <input
                aria-describedby={error ? "login-error" : undefined}
                aria-invalid={error ? true : undefined}
                autoComplete="one-time-code"
                autoFocus
                className="min-h-11 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-canvas)] py-2 pl-10 pr-3 text-sm text-[var(--sh-ink-strong)] outline-none transition-colors focus:border-[var(--sh-brand-500)] focus:ring-2 focus:ring-[var(--sh-brand-100)]"
                id="access-code"
                maxLength={512}
                onChange={(event) => setAccessCode(event.target.value)}
                type="password"
                value={accessCode}
              />
            </div>
            {error ? (
              <p
                className="mt-2 text-sm text-[var(--sh-danger-strong)]"
                id="login-error"
                role="alert"
              >
                {error}
              </p>
            ) : null}
            {status === "unavailable" && !error ? (
              <div className="mt-3 flex items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] px-3 py-2 text-sm text-[var(--sh-danger-strong)]">
                <span>登录服务暂时不可用</span>
                <Button
                  aria-label="重新连接登录服务"
                  onClick={() => void refresh().catch(() => undefined)}
                  size="sm"
                  variant="quiet"
                >
                  <RotateCw aria-hidden="true" />
                  重试
                </Button>
              </div>
            ) : null}
            <Button
              className="mt-6 w-full"
              disabled={status === "loading"}
              loading={submitting || status === "loading"}
              loadingText={submitting ? "正在登录" : "正在恢复会话"}
              size="lg"
              type="submit"
            >
              <LogIn aria-hidden="true" />
              登录
            </Button>
          </form>
        </section>
      </main>
    </div>
  );
}
