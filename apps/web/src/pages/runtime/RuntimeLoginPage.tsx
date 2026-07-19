import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { LoginBrandLockup, LoginVisualPanel } from "@/pages/auth/LoginBrandVisual";
import { ThemeSwitcher } from "@/shared/theme/ThemeSwitcher";
import { buttonVariants } from "@/shared/ui/Button";

/** Real mode deliberately does not invent a login API that the contract does not provide. */
export function RuntimeLoginPage() {
  return (
    <div className="relative grid min-h-screen bg-[var(--sh-surface-canvas)] lg:grid-cols-[minmax(0,1.08fr)_minmax(440px,0.92fr)]">
      <div className="absolute right-4 top-4 z-20 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)]/88 shadow-[var(--sh-shadow-card)] backdrop-blur-sm lg:right-6 lg:top-6">
        <ThemeSwitcher showLabel />
      </div>
      <LoginVisualPanel />
      <main className="flex items-center justify-center px-4 py-20 sm:px-6 lg:py-24">
        <section className="w-full max-w-[440px] rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 shadow-[var(--sh-shadow-floating)] sm:p-8">
          <LoginBrandLockup />
          <h1 className="mt-7 text-2xl font-semibold text-[var(--sh-ink-strong)]">
            使用学校账户进入
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
            登录由学校统一管理。完成登录后，回到这里即可继续准备课程。
          </p>
          <Link className={`${buttonVariants()} mt-7 w-full`} to="/app/projects">
            返回课堂工作区
            <ArrowRight aria-hidden="true" />
          </Link>
          <p className="mt-4 text-center text-xs leading-5 text-[var(--sh-ink-faint)]">
            如果你已经登录，请直接返回课堂工作区；若页面仍为空，请联系学校管理员。
          </p>
        </section>
      </main>
    </div>
  );
}
