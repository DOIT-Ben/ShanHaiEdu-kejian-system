import { http } from "msw";
import { db } from "../db";
import { API, ok, requireSession, simulateLatency } from "../http";
import { isTaskActive } from "@/shared/lib/status";
import { stepKeyForNode } from "@/entities/workflow/steps";

/** 主页聚合：继续创作、待处理（只列可行动事项）、最近成果、运行任务。 */
export const homeHandlers = [
  http.get(API("/home/overview"), async () => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;

    const projects = [...db.projects.values()].sort((a, b) =>
      b.updated_at.localeCompare(a.updated_at),
    );

    const continueItems = projects
      .filter((p) => p.status !== "archived")
      .map((project) => {
        const lessons = [...db.lessons.values()]
          .filter((l) => l.project_id === project.id)
          .sort((a, b) => a.position - b.position);
        const material = db.materials.get(project.id);
        if (!material) {
          return {
            project_id: project.id,
            project_title: project.title,
            lesson_id: null,
            lesson_title: null,
            next_action: "上传教材，开始创作",
            next_url: `/app/projects/${project.id}/materials`,
            progress_summary: "教材尚未上传",
            cover_asset_url: null,
            updated_at: project.updated_at,
          };
        }
        const pending = lessons.find((l) =>
          Object.values(l.branches).some(
            (b) => b.state === "review_required" || b.state === "in_progress",
          ),
        );
        const lesson = pending ?? lessons[0] ?? null;
        let nextAction = "查看项目";
        let nextUrl = `/app/projects/${project.id}`;
        if (lesson) {
          const branchEntries = Object.entries(lesson.branches) as [string, typeof lesson.branches.lesson_plan][];
          const actionable = branchEntries.find(([, b]) => b.state === "review_required") ??
            branchEntries.find(([, b]) => b.state === "in_progress");
          if (actionable) {
            const [, branchState] = actionable;
            nextAction = branchState.summary ?? "继续制作";
            nextUrl = branchState.next_step_key
              ? `/app/projects/${project.id}/lessons/${lesson.id}/work/${branchState.next_step_key}`
              : `/app/projects/${project.id}/lessons/${lesson.id}`;
          }
        }
        const cover = [...db.assets.values()].find(
          (a) => a.project_id === project.id && a.kind === "image",
        );
        return {
          project_id: project.id,
          project_title: project.title,
          lesson_id: lesson?.id ?? null,
          lesson_title: lesson?.title ?? null,
          next_action: nextAction,
          next_url: nextUrl,
          progress_summary: lesson ? `${lessons.length} 个课时` : null,
          cover_asset_url: cover?.preview_url ?? null,
          updated_at: project.updated_at,
        };
      });

    const pendingActions: {
      kind: "review_required" | "cover_selection" | "shot_failed" | "delivery_ready" | "budget_pause" | "stale_content";
      title: string;
      detail: string | null;
      url: string;
      project_title: string | null;
      occurred_at: string | null;
    }[] = [];

    for (const run of db.nodeRuns.values()) {
      const project = db.projects.get(run.project_id);
      if (!project || !run.lesson_id) continue;
      const stepKey = stepKeyForNode(run.node_key, run.status);
      const base = `/app/projects/${run.project_id}/lessons/${run.lesson_id}/work/${stepKey}`;
      if (run.status === "review_required") {
        pendingActions.push({
          kind: run.node_key === "ppt_cover" ? "cover_selection" : "review_required",
          title: run.node_key === "ppt_cover" ? `${project.title}：PPT 封面待选择` : `${project.title}：${run.title}等待你确认`,
          detail: null,
          url: base,
          project_title: project.title,
          occurred_at: run.updated_at,
        });
      }
      if (run.status === "stale") {
        pendingActions.push({
          kind: "stale_content",
          title: `${project.title}：${run.title}内容已变化`,
          detail: "上游已更新，建议重新生成或确认继续使用当前版本。",
          url: base,
          project_title: project.title,
          occurred_at: run.updated_at,
        });
      }
    }
    for (const shot of db.shots.values()) {
      if (shot.status !== "failed") continue;
      const vp = db.videoProjects.get(shot.video_project_id);
      const lesson = vp ? db.lessons.get(vp.lesson_id) : null;
      if (!vp || !lesson) continue;
      pendingActions.push({
        kind: "shot_failed",
        title: `镜头${shot.position}生成失败，可重试`,
        detail: shot.failure_reason,
        url: `/app/projects/${lesson.project_id}/lessons/${lesson.id}/work/video-clips`,
        project_title: db.projects.get(lesson.project_id)?.title ?? null,
        occurred_at: null,
      });
    }
    for (const automation of db.automations.values()) {
      if (automation.state !== "paused" || automation.paused_reason !== "budget_confirmation_required") continue;
      const project = db.projects.get(automation.project_id);
      if (!project) continue;
      pendingActions.push({
        kind: "budget_pause",
        title: `${project.title}：自动执行等待费用确认`,
        detail: automation.paused_detail,
        url: `/app/projects/${project.id}`,
        project_title: project.title,
        occurred_at: null,
      });
    }
    for (const delivery of db.deliveries.values()) {
      if (delivery.status !== "packaged") continue;
      const project = db.projects.get(delivery.project_id);
      if (!project) continue;
      pendingActions.push({
        kind: "delivery_ready",
        title: `${project.title}：交付包可下载`,
        detail: null,
        url: `/app/projects/${project.id}/delivery`,
        project_title: project.title,
        occurred_at: null,
      });
    }

    const recentArtifacts = [...db.assets.values()]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .slice(0, 8)
      .map((asset) => ({
        id: asset.id,
        kind: asset.kind === "video_clip" ? ("video_clip" as const) : asset.kind === "ppt_page" ? ("ppt_page" as const) : asset.kind === "document" ? ("document" as const) : asset.kind === "audio" ? ("audio" as const) : ("image" as const),
        title: asset.title,
        preview_url: asset.preview_url,
        project_title: db.projects.get(asset.project_id)?.title ?? null,
        url: `/app/projects/${asset.project_id}/results`,
      }));

    const runningJobs = [...db.jobs.values()]
      .filter((job) => isTaskActive(job.status))
      .map(({ plan: _plan, ...job }) => job);

    const isNewUser = continueItems.length === 0;

    return ok({
      is_new_user: isNewUser,
      continue_items: continueItems.slice(0, 3),
      pending_actions: pendingActions.slice(0, 8),
      recent_artifacts: recentArtifacts,
      running_jobs: runningJobs,
    });
  }),
];
