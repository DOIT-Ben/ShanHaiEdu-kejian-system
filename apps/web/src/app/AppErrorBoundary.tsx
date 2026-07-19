import { Component, type PropsWithChildren } from "react";
import { RefreshCcw } from "lucide-react";
import { useLocation } from "react-router-dom";

type AppErrorBoundaryState = { failed: boolean };

export class AppErrorBoundary extends Component<PropsWithChildren, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch() {
    // Error reporting belongs to the production observability adapter.
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--sh-surface-canvas)] px-6 py-12">
        <section className="w-full max-w-lg rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-8 text-center shadow-[var(--sh-shadow-card)]">
          <div
            className="mx-auto grid size-14 place-items-center rounded-full bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]"
            aria-hidden="true"
          >
            <RefreshCcw aria-hidden="true" className="size-7" />
          </div>
          <h1 className="mt-5 text-2xl font-semibold text-[var(--sh-ink-strong)]">
            页面暂时无法打开
          </h1>
          <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
            已保存的内容不会受到影响。可以重新加载当前页面，或先返回工作台首页继续其他内容。
          </p>
          <div className="mt-7 flex flex-wrap justify-center gap-3">
            <button
              className="min-h-11 rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-600)] px-5 text-sm font-semibold text-white"
              onClick={() => window.location.reload()}
              type="button"
            >
              重新加载
            </button>
            <a
              className="inline-flex min-h-11 items-center rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-default)] px-5 text-sm font-semibold text-[var(--sh-brand-700)]"
              href="/app"
            >
              返回工作台首页
            </a>
          </div>
        </section>
      </main>
    );
  }
}

export function RouteErrorBoundary({ children }: PropsWithChildren) {
  const location = useLocation();
  return <AppErrorBoundary key={location.key}>{children}</AppErrorBoundary>;
}
