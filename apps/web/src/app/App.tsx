import { lazy, Suspense } from "react";

const RuntimeApp = lazy(() =>
  import("@/app/RuntimeApp").then((module) => ({ default: module.RuntimeApp })),
);

function AppLoading() {
  return (
    <div className="grid min-h-screen place-items-center bg-[var(--sh-surface-canvas)]">
      <div className="text-center" role="status">
        <span className="mx-auto block size-9 animate-pulse rounded-full bg-[var(--sh-brand-100)] motion-reduce:animate-none" />
        <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">正在打开课堂作品</p>
      </div>
    </div>
  );
}

export function App() {
  return (
    <Suspense fallback={<AppLoading />}>
      <RuntimeApp />
    </Suspense>
  );
}
