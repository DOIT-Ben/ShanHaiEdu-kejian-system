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
const RuntimeMaterialsPage = lazy(() =>
  import("@/pages/projects/RuntimeMaterialsPage").then((module) => ({
    default: module.RuntimeMaterialsPage,
  })),
);
const RuntimeLessonsPage = lazy(() =>
  import("@/pages/projects/RuntimeLessonsPage").then((module) => ({
    default: module.RuntimeLessonsPage,
  })),
);
const RuntimeJobPage = lazy(() =>
  import("@/pages/projects/RuntimeJobPage").then((module) => ({
    default: module.RuntimeJobPage,
  })),
);
const RuntimeAssetsPage = lazy(() =>
  import("@/pages/projects/RuntimeAssetsPage").then((module) => ({
    default: module.RuntimeAssetsPage,
  })),
);
const RuntimeArtifactPage = lazy(() =>
  import("@/pages/projects/RuntimeArtifactPage").then((module) => ({
    default: module.RuntimeArtifactPage,
  })),
);
const RuntimeLessonWorkbenchPage = lazy(() =>
  import("@/pages/projects/RuntimeLessonWorkbenchPage").then((module) => ({
    default: module.RuntimeLessonWorkbenchPage,
  })),
);
const CreationHomePage = lazy(() =>
  import("@/pages/creation/CreationHomePage").then((module) => ({
    default: module.CreationHomePage,
  })),
);
const CreationStudioPage = lazy(() =>
  import("@/pages/creation/CreationStudioPage").then((module) => ({
    default: module.CreationStudioPage,
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
              <Route element={<HomePage />} index />
              <Route element={<ProjectsPage />} path="projects" />
              <Route element={<RuntimeNewProjectPage />} path="projects/new" />
              <Route element={<RuntimeProjectSetupPage />} path="projects/:projectId/setup" />
              <Route element={<RuntimeProjectOverviewPage />} path="projects/:projectId" />
              <Route
                element={<RuntimeMaterialsPage />}
                path="projects/:projectId/materials/:materialId?"
              />
              <Route element={<RuntimeLessonsPage />} path="projects/:projectId/lessons" />
              <Route element={<RuntimeAssetsPage />} path="projects/:projectId/assets" />
              <Route
                element={<RuntimeArtifactPage />}
                path="projects/:projectId/artifacts/:artifactId"
              />
              <Route element={<RuntimeJobPage />} path="projects/:projectId/jobs/:jobId" />
              <Route
                element={<RuntimeLessonWorkbenchPage />}
                path="projects/:projectId/lessons/:lessonId/work/:stepKey"
              />
              <Route element={<RuntimeUnavailablePage />} path="projects/:projectId/*" />
              <Route element={<CreationHomePage />} path="creation" />
              <Route element={<CreationStudioPage />} path="creation/:studioPath" />
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
