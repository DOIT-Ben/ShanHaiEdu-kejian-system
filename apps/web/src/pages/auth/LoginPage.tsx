import { ArrowRight, BookOpenCheck, Waves } from "lucide-react";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/shared/ui/Button";
import { ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import {
  getMockLoginDefaults,
  mockAuthEnabled,
  MockAuthError,
  MockAuthUnavailableError,
  signIn,
} from "@/shared/auth/mockAuth";

const loginDefaults = getMockLoginDefaults();

export function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  return (
    <div className="relative grid min-h-screen bg-[var(--sh-surface-canvas)] lg:grid-cols-[1.05fr_0.95fr]">
      <div className="absolute right-4 top-4 z-20 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/88 shadow-[var(--sh-shadow-card)] backdrop-blur-sm lg:right-6 lg:top-6">
        <ThemeSwitcher showLabel />
      </div>
      <section className="hidden items-center justify-center overflow-hidden bg-[var(--sh-surface-inverse)] p-12 text-white lg:flex">
        <div className="max-w-xl">
          <span className="grid size-12 place-items-center rounded-[var(--sh-radius-sm)] bg-white/10">
            <Waves aria-hidden="true" className="size-6" />
          </span>
          <h1 className="mt-8 text-[42px] font-bold leading-tight text-white">
            把教材变成完整的课堂作品
          </h1>
          <p className="mt-5 max-w-lg leading-7 text-white/70">
            在同一处完成课时、教案、PPT、课堂导入视频与最终交付。
          </p>
          <div className="relative mt-10 pb-10 pr-10">
            <div className="rotate-[1.5deg] overflow-hidden rounded-[var(--sh-radius-lg)] border-[7px] border-[var(--sh-artifact-paper)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-modal)]">
              <img
                alt="认识百分数课堂课件封面"
                className="aspect-video w-full object-cover"
                src="/assets/creation/slide-percent-cover.svg"
              />
            </div>
            <div className="absolute -bottom-2 right-0 w-[38%] -rotate-[4deg] overflow-hidden rounded-[var(--sh-radius-md)] border-[5px] border-[var(--sh-artifact-paper)] bg-[var(--sh-artifact-paper)] shadow-[var(--sh-shadow-floating)]">
              <img
                alt="果汁标签观察教学插画"
                className="aspect-[4/3] w-full object-cover"
                src="/assets/creation/juice-observation.svg"
              />
            </div>
          </div>
        </div>
      </section>
      <main className="flex items-center justify-center p-6">
        <form
          className="w-full max-w-md rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-7 shadow-[var(--sh-shadow-card)]"
          onSubmit={(event) => {
            event.preventDefault();
            if (!mockAuthEnabled) {
              setError("当前暂时无法登录，请稍后重试或联系学校管理员。");
              return;
            }
            const form = new FormData(event.currentTarget);
            const readText = (value: FormDataEntryValue | null) =>
              typeof value === "string" ? value : "";
            try {
              const session = signIn({
                email: readText(form.get("email")),
                password: readText(form.get("password")),
              });
              const requested = (location.state as { from?: { pathname?: string } } | null)?.from
                ?.pathname;
              const target =
                requested?.startsWith("/admin") && session.user.role !== "admin"
                  ? "/app"
                  : (requested ?? (session.user.role === "admin" ? "/admin" : "/app"));
              void navigate(target, { replace: true });
            } catch (reason) {
              setNotice("");
              setError(
                reason instanceof MockAuthError || reason instanceof MockAuthUnavailableError
                  ? reason.message
                  : "暂时无法登录，请重试",
              );
            }
          }}
        >
          <span className="grid size-11 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
            <BookOpenCheck aria-hidden="true" className="size-5" />
          </span>
          <h2 className="mt-6 text-2xl font-bold text-[var(--sh-ink-strong)]">登录山海教育</h2>
          <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
            {mockAuthEnabled ? "继续你的课堂作品" : "登录服务正在准备中"}
          </p>
          {!mockAuthEnabled ? (
            <p
              className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-4 text-sm leading-6 text-[var(--sh-ink-default)]"
              role="status"
            >
              当前暂时无法登录，请稍后重试或联系学校管理员。
            </p>
          ) : (
            <p className="mt-5 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-3 text-xs leading-5 text-[var(--sh-brand-700)]">
              当前为体验环境，体验账号已自动填写，不会连接学校正式账号。
            </p>
          )}
          <label className="mt-7 block">
            <span className="text-sm font-semibold">账号</span>
            <input
              className="mt-2 min-h-11 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 outline-none focus:border-[var(--sh-brand-500)]"
              defaultValue={loginDefaults.email}
              disabled={!mockAuthEnabled}
              name="email"
              type="email"
            />
          </label>
          <label className="mt-4 block">
            <span className="text-sm font-semibold">密码</span>
            <input
              className="mt-2 min-h-11 w-full rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-3 outline-none focus:border-[var(--sh-brand-500)]"
              defaultValue={loginDefaults.password}
              disabled={!mockAuthEnabled}
              name="password"
              type="password"
            />
          </label>
          {error ? (
            <p
              className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-3 text-sm text-[var(--sh-danger)]"
              role="alert"
            >
              {error}
            </p>
          ) : null}
          {notice ? (
            <p
              className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] p-3 text-sm text-[var(--sh-brand-700)]"
              role="status"
            >
              {notice}
            </p>
          ) : null}
          <Button className="mt-6 w-full" disabled={!mockAuthEnabled} size="lg" type="submit">
            {mockAuthEnabled ? "登录" : "登录暂不可用"}
            <ArrowRight aria-hidden="true" />
          </Button>
          <button
            className="mt-4 w-full text-center text-sm font-semibold text-[var(--sh-brand-600)]"
            onClick={() => {
              setError("");
              setNotice("请联系学校管理员重置密码。");
            }}
            type="button"
          >
            忘记密码
          </button>
        </form>
      </main>
    </div>
  );
}
