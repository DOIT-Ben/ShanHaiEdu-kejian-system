import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { RouteErrorBoundary } from "@/app/AppErrorBoundary";
import { RequireAdmin, RequireSession } from "@/shared/auth/RouteGuards";

const AdminLayout = lazy(() =>
  import("@/layouts/AdminLayout").then((module) => ({ default: module.AdminLayout })),
);
const GlobalAppShell = lazy(() =>
  import("@/layouts/GlobalAppShell").then((module) => ({ default: module.GlobalAppShell })),
);
const ProjectOverviewLayout = lazy(() =>
  import("@/layouts/ProjectOverviewLayout").then((module) => ({
    default: module.ProjectOverviewLayout,
  })),
);
const ProjectWorkbenchLayout = lazy(() =>
  import("@/layouts/ProjectWorkbenchLayout").then((module) => ({
    default: module.ProjectWorkbenchLayout,
  })),
);
const AdminAuditPage = lazy(() =>
  import("@/pages/admin/AdminAuditPage").then((module) => ({ default: module.AdminAuditPage })),
);
const AdminContentPage = lazy(() =>
  import("@/pages/admin/AdminContentPage").then((module) => ({
    default: module.AdminContentPage,
  })),
);
const AdminModelsPage = lazy(() =>
  import("@/pages/admin/AdminModelsPage").then((module) => ({
    default: module.AdminModelsPage,
  })),
);
const AdminUsagePage = lazy(() =>
  import("@/pages/admin/AdminUsagePage").then((module) => ({ default: module.AdminUsagePage })),
);
const AdminUsersPage = lazy(() =>
  import("@/pages/admin/AdminUsersPage").then((module) => ({ default: module.AdminUsersPage })),
);
const AdminWorkflowsPage = lazy(() =>
  import("@/pages/admin/AdminWorkflowsPage").then((module) => ({
    default: module.AdminWorkflowsPage,
  })),
);
const LoginPage = lazy(() =>
  import("@/pages/auth/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const CreationBatchPage = lazy(() =>
  import("@/pages/creation/CreationBatchPage").then((module) => ({
    default: module.CreationBatchPage,
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
const HomePage = lazy(() =>
  import("@/pages/home/HomePage").then((module) => ({ default: module.HomePage })),
);
const NotFoundPage = lazy(() =>
  import("@/pages/NotFoundPage").then((module) => ({ default: module.NotFoundPage })),
);
const DeliveryPage = lazy(() =>
  import("@/pages/projects/DeliveryPage").then((module) => ({ default: module.DeliveryPage })),
);
const LessonsPage = lazy(() =>
  import("@/pages/projects/LessonsPage").then((module) => ({ default: module.LessonsPage })),
);
const NewProjectPage = lazy(() =>
  import("@/pages/projects/NewProjectPage").then((module) => ({
    default: module.NewProjectPage,
  })),
);
const ProjectMaterialsPage = lazy(() =>
  import("@/pages/projects/ProjectMaterialsPage").then((module) => ({
    default: module.ProjectMaterialsPage,
  })),
);
const ProjectOverviewPage = lazy(() =>
  import("@/pages/projects/ProjectOverviewPage").then((module) => ({
    default: module.ProjectOverviewPage,
  })),
);
const ProjectResultsPage = lazy(() =>
  import("@/pages/projects/ProjectResultsPage").then((module) => ({
    default: module.ProjectResultsPage,
  })),
);
const ProjectsPage = lazy(() =>
  import("@/pages/projects/ProjectsPage").then((module) => ({ default: module.ProjectsPage })),
);
const ProjectTasksPage = lazy(() =>
  import("@/pages/projects/ProjectTasksPage").then((module) => ({
    default: module.ProjectTasksPage,
  })),
);
const WorkStepPage = lazy(() =>
  import("@/pages/projects/WorkStepPage").then((module) => ({ default: module.WorkStepPage })),
);
const TasksPage = lazy(() =>
  import("@/pages/tasks/TasksPage").then((module) => ({ default: module.TasksPage })),
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

export function MockApp() {
  return (
    <BrowserRouter>
      <RouteErrorBoundary>
        <Suspense fallback={<AppLoading />}>
          <Routes>
            <Route element={<LoginPage />} path="/login" />
            <Route element={<RequireSession />}>
              <Route element={<GlobalAppShell />} path="/app">
                <Route
                  element={
                    <HomePage
                      attentionItems={[
                        {
                          detail: "认识百分数 · 第 1 课时",
                          label: "教案待确认",
                          status: "review",
                          to: "/app/tasks",
                        },
                      ]}
                      recentResults={[
                        {
                          label: "果汁标签观察图",
                          ratio: "4:3",
                          to: "/app/creation/images",
                          type: "image",
                          variant: 0,
                        },
                        {
                          label: "百分数百格图",
                          page: 2,
                          to: "/app/creation/presentations",
                          type: "presentation",
                          variant: 0,
                        },
                        {
                          label: "课堂首问关键帧",
                          to: "/app/creation/videos",
                          type: "video",
                          variant: 1,
                        },
                      ]}
                    />
                  }
                  index
                />
                <Route element={<ProjectsPage />} path="projects" />
                <Route element={<NewProjectPage />} path="projects/new" />
                <Route
                  element={<ProjectWorkbenchLayout />}
                  path="projects/:projectId/lessons/:lessonId/work"
                >
                  <Route element={<WorkStepPage />} path=":stepKey" />
                </Route>
                <Route element={<ProjectOverviewLayout />} path="projects/:projectId">
                  <Route element={<ProjectOverviewPage />} index />
                  <Route element={<ProjectMaterialsPage />} path="materials" />
                  <Route element={<LessonsPage />} path="lessons" />
                  <Route
                    element={<Navigate replace to="work/lesson-plan" />}
                    path="lessons/:lessonId"
                  />
                  <Route element={<ProjectResultsPage />} path="results" />
                  <Route element={<ProjectTasksPage />} path="tasks" />
                  <Route element={<DeliveryPage />} path="delivery" />
                </Route>
                <Route element={<CreationHomePage />} path="creation" />
                <Route element={<CreationStudioPage type="image" />} path="creation/images" />
                <Route element={<CreationStudioPage type="video" />} path="creation/videos" />
                <Route
                  element={<CreationStudioPage type="presentation" />}
                  path="creation/presentations"
                />
                <Route element={<CreationBatchPage />} path="creation/batches/:batchId" />
                <Route
                  element={<CreationBatchPage />}
                  path="projects/:projectId/lessons/:lessonId/creation-batches/:batchId"
                />
                <Route element={<TasksPage />} path="tasks" />
              </Route>
            </Route>
            <Route element={<RequireAdmin />}>
              <Route element={<AdminLayout />} path="/admin">
                <Route element={<Navigate replace to="content" />} index />
                <Route element={<AdminContentPage />} path="content" />
                <Route element={<AdminWorkflowsPage />} path="workflows" />
                <Route element={<AdminModelsPage />} path="models" />
                <Route element={<AdminUsagePage />} path="usage" />
                <Route element={<AdminUsersPage />} path="users" />
                <Route element={<AdminAuditPage />} path="audit" />
              </Route>
            </Route>
            <Route element={<Navigate replace to="/app" />} path="/" />
            <Route element={<NotFoundPage />} path="*" />
          </Routes>
        </Suspense>
      </RouteErrorBoundary>
    </BrowserRouter>
  );
}
