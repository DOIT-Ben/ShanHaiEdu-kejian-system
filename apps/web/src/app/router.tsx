import { createBrowserRouter, Navigate } from "react-router";
import { RedirectIfAuthed, RequireAdmin, RequireAuth } from "./guards";
import { AppLayout } from "@/layouts/app-layout";
import { AdminLayout } from "@/layouts/admin-layout";
import { ProjectLayout } from "@/layouts/project-layout";
import { LoginPage } from "@/pages/login-page";
import { HomePage } from "@/pages/home-page";
import { ProjectListPage } from "@/pages/projects/project-list-page";
import { ProjectCreatePage } from "@/pages/projects/project-create-page";
import { ProjectOverviewPage } from "@/pages/projects/project-overview-page";
import { TextbookPage } from "@/pages/projects/textbook-page";
import { LessonDivisionPage } from "@/pages/projects/lesson-division-page";
import { LessonListPage } from "@/pages/projects/lesson-list-page";
import { ProjectAssetsPage } from "@/pages/projects/project-assets-page";
import { ProjectTasksPage } from "@/pages/projects/project-tasks-page";
import { ProjectDeliveryPage } from "@/pages/projects/project-delivery-page";
import { ProjectSettingsPage } from "@/pages/projects/project-settings-page";
import { LessonEntryPage } from "@/pages/workbench/lesson-entry-page";
import { WorkbenchPage } from "@/pages/workbench/workbench-page";
import { AdminDashboardPage } from "@/pages/admin/admin-dashboard-page";
import { AdminTemplatesPage } from "@/pages/admin/admin-templates-page";
import { AdminTemplateDetailPage } from "@/pages/admin/admin-template-detail-page";
import { AdminGatewayLayout } from "@/pages/admin/admin-gateway-layout";
import { AdminProvidersPage } from "@/pages/admin/admin-providers-page";
import { AdminModelsPage } from "@/pages/admin/admin-models-page";
import { AdminRoutesPage } from "@/pages/admin/admin-routes-page";
import { AdminBudgetsPage } from "@/pages/admin/admin-budgets-page";
import { AdminModelRunsPage } from "@/pages/admin/admin-model-runs-page";
import { AdminWorkflowsPage } from "@/pages/admin/admin-workflows-page";
import { AdminUsersPage } from "@/pages/admin/admin-users-page";
import { AdminAuditPage } from "@/pages/admin/admin-audit-page";
import { ForbiddenPage, NotFoundPage, SystemErrorPage } from "@/pages/errors/error-pages";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/app" replace /> },
  {
    path: "/login",
    element: (
      <RedirectIfAuthed>
        <LoginPage />
      </RedirectIfAuthed>
    ),
    errorElement: <SystemErrorPage />,
  },
  {
    path: "/app",
    element: (
      <RequireAuth>
        <AppLayout />
      </RequireAuth>
    ),
    errorElement: <SystemErrorPage />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "projects", element: <ProjectListPage /> },
      { path: "projects/new", element: <ProjectCreatePage /> },
      {
        path: "projects/:projectId",
        element: <ProjectLayout />,
        children: [
          { index: true, element: <ProjectOverviewPage /> },
          { path: "textbook", element: <TextbookPage /> },
          { path: "lesson-division", element: <LessonDivisionPage /> },
          { path: "lessons", element: <LessonListPage /> },
          { path: "assets", element: <ProjectAssetsPage /> },
          { path: "tasks", element: <ProjectTasksPage /> },
          { path: "delivery", element: <ProjectDeliveryPage /> },
          { path: "settings", element: <ProjectSettingsPage /> },
        ],
      },
      // 工作台是全屏三栏布局，不嵌入项目二级导航
      { path: "projects/:projectId/lessons/:lessonId", element: <LessonEntryPage /> },
      { path: "projects/:projectId/lessons/:lessonId/workbench/:nodeKey", element: <WorkbenchPage /> },
    ],
  },
  {
    path: "/admin",
    element: (
      <RequireAdmin>
        <AdminLayout />
      </RequireAdmin>
    ),
    errorElement: <SystemErrorPage />,
    children: [
      { index: true, element: <AdminDashboardPage /> },
      { path: "templates", element: <AdminTemplatesPage /> },
      { path: "templates/:templateId", element: <AdminTemplateDetailPage /> },
      {
        path: "model-gateway",
        element: <AdminGatewayLayout />,
        children: [
          { index: true, element: <Navigate to="providers" replace /> },
          { path: "providers", element: <AdminProvidersPage /> },
          { path: "models", element: <AdminModelsPage /> },
          { path: "routes", element: <AdminRoutesPage /> },
          { path: "budgets", element: <AdminBudgetsPage /> },
          { path: "runs", element: <AdminModelRunsPage /> },
        ],
      },
      { path: "workflows", element: <AdminWorkflowsPage /> },
      { path: "users", element: <AdminUsersPage /> },
      { path: "audit", element: <AdminAuditPage /> },
    ],
  },
  { path: "/403", element: <ForbiddenPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
