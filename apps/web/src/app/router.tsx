import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, Outlet } from "react-router";
import { RequireAdmin, RequireAuth } from "./session";
import { GlobalAppShell } from "@/layouts/GlobalAppShell";
import { Spinner } from "@/shared/ui";

const LoginPage = lazy(() => import("@/pages/login/LoginPage"));
const HomePage = lazy(() => import("@/pages/home/HomePage"));
const ProjectListPage = lazy(() => import("@/pages/projects/ProjectListPage"));
const ProjectCreatePage = lazy(() => import("@/pages/projects/ProjectCreatePage"));
const ProjectLayout = lazy(() => import("@/layouts/ProjectLayout"));
const ProjectOverviewPage = lazy(() => import("@/pages/project/ProjectOverviewPage"));
const MaterialsPage = lazy(() => import("@/pages/project/MaterialsPage"));
const LessonListPage = lazy(() => import("@/pages/project/LessonListPage"));
const LessonEntryPage = lazy(() => import("@/pages/workbench/LessonEntryPage"));
const WorkbenchPage = lazy(() => import("@/pages/workbench/WorkbenchPage"));
const ProjectResultsPage = lazy(() => import("@/pages/project/ProjectResultsPage"));
const ProjectTasksPage = lazy(() => import("@/pages/project/ProjectTasksPage"));
const DeliveryPage = lazy(() => import("@/pages/project/DeliveryPage"));
const CreationHomePage = lazy(() => import("@/pages/creation/CreationHomePage"));
const StudioPage = lazy(() => import("@/pages/creation/StudioPage"));
const BatchDetailPage = lazy(() => import("@/pages/creation/BatchDetailPage"));
const TaskCenterPage = lazy(() => import("@/pages/tasks/TaskCenterPage"));
const AdminLayout = lazy(() => import("@/layouts/AdminLayout"));
const AdminContentPage = lazy(() => import("@/pages/admin/AdminContentPage"));
const AdminContentDetailPage = lazy(() => import("@/pages/admin/AdminContentDetailPage"));
const AdminWorkflowsPage = lazy(() => import("@/pages/admin/AdminWorkflowsPage"));
const AdminModelsPage = lazy(() => import("@/pages/admin/AdminModelsPage"));
const AdminUsagePage = lazy(() => import("@/pages/admin/AdminUsagePage"));
const AdminUsersPage = lazy(() => import("@/pages/admin/AdminUsersPage"));
const AdminAuditPage = lazy(() => import("@/pages/admin/AdminAuditPage"));
const NotFoundPage = lazy(() => import("@/pages/NotFoundPage"));

function PageFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-ink-muted">
      <Spinner className="size-5" />
    </div>
  );
}

function suspense(node: ReactNode) {
  return <Suspense fallback={<PageFallback />}>{node}</Suspense>;
}

/** 路由即页面地图（docs/frontend/07 §1）；URL 可直达、可刷新恢复。 */
export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/app" replace /> },
  { path: "/login", element: suspense(<LoginPage />) },
  {
    path: "/app",
    element: (
      <RequireAuth>
        <GlobalAppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: suspense(<HomePage />) },
      { path: "projects", element: suspense(<ProjectListPage />) },
      { path: "projects/new", element: suspense(<ProjectCreatePage />) },
      {
        path: "projects/:projectId",
        element: suspense(<ProjectLayout />),
        children: [
          { index: true, element: suspense(<ProjectOverviewPage />) },
          { path: "materials", element: suspense(<MaterialsPage />) },
          { path: "lessons", element: suspense(<LessonListPage />) },
          { path: "lessons/:lessonId", element: suspense(<LessonEntryPage />) },
          { path: "lessons/:lessonId/work/:stepKey", element: suspense(<WorkbenchPage />) },
          { path: "results", element: suspense(<ProjectResultsPage />) },
          { path: "tasks", element: suspense(<ProjectTasksPage />) },
          { path: "delivery", element: suspense(<DeliveryPage />) },
        ],
      },
      {
        path: "creation",
        element: <Outlet />,
        children: [
          { index: true, element: suspense(<CreationHomePage />) },
          { path: "images", element: suspense(<StudioPage studioType="image" />) },
          { path: "videos", element: suspense(<StudioPage studioType="video" />) },
          { path: "presentations", element: suspense(<StudioPage studioType="presentation" />) },
          { path: "batches/:batchId", element: suspense(<BatchDetailPage />) },
        ],
      },
      { path: "tasks", element: suspense(<TaskCenterPage />) },
    ],
  },
  {
    path: "/admin",
    element: (
      <RequireAdmin>
        {suspense(<AdminLayout />)}
      </RequireAdmin>
    ),
    children: [
      { index: true, element: <Navigate to="/admin/content" replace /> },
      { path: "content", element: suspense(<AdminContentPage />) },
      { path: "content/:contentPackageId", element: suspense(<AdminContentDetailPage />) },
      { path: "workflows", element: suspense(<AdminWorkflowsPage />) },
      { path: "models", element: suspense(<AdminModelsPage />) },
      { path: "usage", element: suspense(<AdminUsagePage />) },
      { path: "users", element: suspense(<AdminUsersPage />) },
      { path: "audit", element: suspense(<AdminAuditPage />) },
    ],
  },
  { path: "*", element: suspense(<NotFoundPage />) },
]);
