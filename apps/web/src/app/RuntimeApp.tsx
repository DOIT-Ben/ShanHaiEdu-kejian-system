import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RouteErrorBoundary } from "@/app/AppErrorBoundary";
import { RuntimeAppShell } from "@/layouts/RuntimeAppShell";

const HomePage = lazy(() =>
  import("@/pages/home/HomePage").then((module) => ({ default: module.HomePage })),
);
const ProjectsPage = lazy(() =>
  import("@/pages/projects/ProjectsPage").then((module) => ({ default: module.ProjectsPage })),
);
const RuntimeNewProjectPage = lazy(() =>
  import("@/pages/projects/RuntimeNewProjectPage").then((module) => ({
    default: module.RuntimeNewProjectPage,
  })),
);
const RuntimeProjectSetupPage = lazy(() =>
  import("@/pages/projects/RuntimeProjectSetupPage").then((module) => ({
    default: module.RuntimeProjectSetupPage,
  })),
);
const RuntimeProjectOverviewPage = lazy(() =>
  import("@/pages/projects/RuntimeProjectOverviewPage").then((module) => ({
    default: module.RuntimeProjectOverviewPage,
  })),
);
const RuntimeLoginPage = lazy(() =>
  import("@/pages/runtime/RuntimeLoginPage").then((module) => ({
    default: module.RuntimeLoginPage,
  })),
);
const RuntimeUnavailablePage = lazy(() =>
  import("@/pages/runtime/RuntimeUnavailablePage").then((module) => ({
    default: module.RuntimeUnavailablePage,
  })),
);

function RuntimeLoading() {
  return (
    <div className="grid min-h-screen place-items-center bg-[var(--sh-surface-canvas)]">
      <div className="text-center" role="status">
        <span className="mx-auto block size-9 animate-pulse rounded-full bg-[var(--sh-brand-100)] motion-reduce:animate-none" />
        <p className="mt-3 text-sm text-[var(--sh-ink-muted)]">正在打开课堂作品</p>
      </div>
    </div>
  );
}

export function RuntimeApp() {
  return (
    <BrowserRouter>
      <RouteErrorBoundary>
        <Suspense fallback={<RuntimeLoading />}>
          <Routes>
            <Route element={<RuntimeLoginPage />} path="/login" />
            <Route element={<RuntimeAppShell />} path="/app">
              <Route element={<HomePage creationAvailable={false} />} index />
              <Route element={<ProjectsPage />} path="projects" />
              <Route element={<RuntimeNewProjectPage />} path="projects/new" />
              <Route element={<RuntimeProjectSetupPage />} path="projects/:projectId/setup" />
              <Route element={<RuntimeProjectOverviewPage />} path="projects/:projectId" />
              <Route element={<RuntimeUnavailablePage />} path="projects/:projectId/*" />
              <Route element={<RuntimeUnavailablePage />} path="creation/*" />
              <Route element={<RuntimeUnavailablePage />} path="tasks" />
            </Route>
            <Route
              element={<RuntimeUnavailablePage title="管理工作区暂未开放" />}
              path="/admin/*"
            />
            <Route element={<Navigate replace to="/app" />} path="/" />
            <Route element={<RuntimeUnavailablePage title="页面暂未开放" />} path="*" />
          </Routes>
        </Suspense>
      </RouteErrorBoundary>
    </BrowserRouter>
  );
}
