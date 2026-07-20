import { Component, type PropsWithChildren } from "react";
import { RefreshCcw } from "lucide-react";
import { useLocation } from "react-router-dom";
import { Button } from "@/shared/ui/Button";

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
            <Button size="lg" onClick={() => window.location.reload()}>
              重新加载
            </Button>
            <Button asChild size="lg" variant="secondary">
              <a href="/app">返回工作台首页</a>
            </Button>
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
