import { lazy, Suspense } from "react";
import { apiConfig } from "@/shared/api/config";

const RuntimeApp = lazy(() =>
  import("@/app/RuntimeApp").then((module) => ({ default: module.RuntimeApp })),
);
const MockApp = import.meta.env.DEV
  ? lazy(() => import("@/app/MockApp").then((module) => ({ default: module.MockApp })))
  : null;

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
  const useMockApp = import.meta.env.DEV && apiConfig.mode === "mock" && MockApp !== null;
  return <Suspense fallback={<AppLoading />}>{useMockApp ? <MockApp /> : <RuntimeApp />}</Suspense>;
}
