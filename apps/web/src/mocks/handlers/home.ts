import { http } from "msw";
import type { HomeOverview, ReviewItem, Task } from "@/shared/api/types";
import { getNodeDef } from "@/entities/workflow/nodes";
import { getDb } from "../db";
import { api, guard, ok, simulateLatency } from "./http";
import { isTaskActive, type TaskStatus } from "@/shared/lib/status";

export const homeHandlers = [
  http.get(api("/home/overview"), async () => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();

    const pendingReviews: ReviewItem[] = [];
    for (const projectState of db.projects.values()) {
      const project = projectState.project;
      if (project.status === "archived") continue;
      if (projectState.evidence?.status === "needs_review") {
        pendingReviews.push({
          review_id: `rev_${project.project_id}_evidence`,
          project_id: project.project_id,
          project_name: project.name,
          lesson_id: null,
          lesson_title: null,
          node_key: "textbook_evidence",
          artifact_version_id: projectState.evidence.artifact_version_id,
          title: "教材解析结果待确认",
          waiting_since: projectState.evidence.created_at,
        });
      }
      if (projectState.division?.status === "needs_review") {
        pendingReviews.push({
          review_id: `rev_${project.project_id}_division`,
          project_id: project.project_id,
          project_name: project.name,
          lesson_id: null,
          lesson_title: null,
          node_key: "lesson_division",
          artifact_version_id: projectState.division.artifact_version_id,
          title: "课时划分待审核",
          waiting_since: projectState.division.created_at,
        });
      }
      for (const lessonState of projectState.lessons) {
        for (const node of lessonState.nodes.values()) {
          if (node.summary.status === "needs_review" || node.summary.status === "revision_required") {
            const latest = node.artifactVersions[0];
            pendingReviews.push({
              review_id: `rev_${lessonState.lesson.lesson_id}_${node.summary.node_key}`,
              project_id: project.project_id,
              project_name: project.name,
              lesson_id: lessonState.lesson.lesson_id,
              lesson_title: lessonState.lesson.title,
              node_key: node.summary.node_key,
              artifact_version_id: latest?.artifact_version_id ?? null,
              title: `${getNodeDef(node.summary.node_key)?.title ?? node.summary.node_key}待审核`,
              waiting_since: latest?.created_at ?? lessonState.lesson.lesson_id,
            });
          }
        }
      }
    }

    const allTasks = [...db.tasks.values()].sort((a, b) => b.created_at.localeCompare(a.created_at));
    const runningTasks: Task[] = allTasks.filter((t) => isTaskActive(t.status as TaskStatus)).slice(0, 5);
    const failedTasks: Task[] = allTasks.filter((t) => t.status === "failed").slice(0, 5);

    const overview: HomeOverview = {
      recent_projects: [...db.projects.values()]
        .filter((p) => p.project.status !== "archived")
        .sort((a, b) => b.project.updated_at.localeCompare(a.project.updated_at))
        .slice(0, 6)
        .map((p) => p.project),
      pending_reviews: pendingReviews.slice(0, 8),
      running_tasks: runningTasks,
      failed_tasks: failedTasks,
      recent_deliveries: [...db.projects.values()]
        .filter((p) => p.delivery.package_file)
        .map((p) => ({
          project_id: p.project.project_id,
          project_name: p.project.name,
          file_object: p.delivery.package_file!,
          delivered_at: p.delivery.packaged_at ?? p.project.updated_at,
        })),
    };
    return ok(overview);
  }),
];
