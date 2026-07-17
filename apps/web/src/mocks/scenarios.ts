import { http } from "msw";
import { db, nowIso } from "./db";
import { API, fail, ok } from "./http";
import { seedDb } from "./seed";
import { clearAllTimers } from "./engine";
import { ID, uuid } from "./ids";

/**
 * 契约场景（contracts/mock-scenarios.json v1.0，13 个必备场景）。
 * 通过 POST /__scenario 或 URL ?scenario= 切换；切换时重置世界。
 */

export const SCENARIOS = [
  "default",
  "project_empty",
  "lesson_plan_edit",
  "intro_options",
  "prompt_review",
  "node_running",
  "node_partial",
  "node_stale",
  "creation_independent",
  "creation_from_package",
  "save_conflict",
  "sse_recovery",
  "budget_pause",
  "admin_content_publish",
] as const;

export type ScenarioKey = (typeof SCENARIOS)[number];

/** 场景 → 建议入口路由（mock-scenarios.json 的 route 字段）。 */
export const SCENARIO_ROUTES: Record<ScenarioKey, string> = {
  default: "/app",
  project_empty: `/app/projects/${ID.projEmpty}`,
  lesson_plan_edit: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/lesson-plan-confirm`,
  intro_options: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/intro-options`,
  prompt_review: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/lesson-plan`,
  node_running: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/lesson-plan`,
  node_partial: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/video-clips`,
  node_stale: `/app/projects/${ID.projAlpha}/lessons/${ID.lessonA2}/work/intro-options`,
  creation_independent: "/app/creation/images",
  creation_from_package: `/app/creation/batches/${ID.batchFromPackage}`,
  save_conflict: `/app/creation/batches/${ID.batchFromPackage}`,
  sse_recovery: "/app/tasks",
  budget_pause: `/app/projects/${ID.projAuto}`,
  admin_content_publish: "/admin/content",
};

export function applyScenario(scenario: string): boolean {
  if (!(SCENARIOS as readonly string[]).includes(scenario)) return false;
  clearAllTimers();
  seedDb();
  db.scenario = scenario;

  switch (scenario as ScenarioKey) {
    case "default":
      break;

    case "project_empty": {
      // 教材未上传、无课时：项目工作台处于最初始状态
      db.materials.delete(ID.projEmpty);
      break;
    }

    case "lesson_plan_edit": {
      // 教案 review_required（种子即此状态），直接编辑草稿
      break;
    }

    case "intro_options": {
      // 九套方案等待挑选；清除已有选择让选择流程完整可走
      db.introSelections.delete(ID.lessonA2);
      const run = db.nodeRuns.get(ID.nrIntroSelectionA2);
      if (run) run.status = "ready";
      // 视频链路回到未解锁
      for (const key of [
        ID.nrVideoScriptA2,
        ID.nrVideoStoryboardA2,
        ID.nrVideoStyleA2,
        ID.nrVideoAssetsA2,
        ID.nrVideoClipsA2,
        ID.nrVideoComposeA2,
      ]) {
        const videoRun = db.nodeRuns.get(key);
        if (videoRun) {
          videoRun.status = "not_ready";
          videoRun.current_artifact_version_id = null;
        }
      }
      db.videoProjects.delete(ID.videoProjectA2);
      const lesson = db.lessons.get(ID.lessonA2);
      if (lesson) {
        lesson.branches.video = { state: "not_ready", summary: "等待选择导入方案", next_step_key: "intro-selection" };
      }
      break;
    }

    case "prompt_review": {
      // 教案节点回到 ready：查看/编辑提示词后启动生成
      const run = db.nodeRuns.get(ID.nrLessonPlanA2);
      if (run) {
        run.status = "ready";
        run.current_artifact_version_id = null;
      }
      const lesson = db.lessons.get(ID.lessonA2);
      if (lesson) {
        lesson.branches.lesson_plan = { state: "not_ready", summary: "等待生成", next_step_key: "lesson-plan" };
      }
      break;
    }

    case "node_running": {
      // 教案节点长时间 running（不自动完成），用于离开/刷新恢复验证
      const run = db.nodeRuns.get(ID.nrLessonPlanA2);
      if (run) {
        run.status = "running";
        run.current_artifact_version_id = null;
        const jobId = uuid(3001);
        run.active_job_id = jobId;
        db.jobs.set(jobId, {
          id: jobId,
          kind: "lesson_plan",
          status: "running",
          title: "教案：生成",
          project_id: ID.projAlpha,
          lesson_id: ID.lessonA2,
          node_run_id: run.id,
          batch_id: null,
          phase_label: "正在生成",
          completed_items: null,
          total_items: null,
          failed_item_keys: [],
          error: null,
          created_at: nowIso(),
          updated_at: nowIso(),
          finished_at: null,
        });
      }
      break;
    }

    case "node_partial": {
      // 种子已含镜头2失败；补一个 partially_completed 任务记录
      const jobId = uuid(3002);
      db.jobs.set(jobId, {
        id: jobId,
        kind: "video_shot_batch",
        status: "partially_completed",
        title: "生成镜头候选（3 项）",
        project_id: ID.projAlpha,
        lesson_id: ID.lessonA2,
        node_run_id: ID.nrVideoClipsA2,
        batch_id: null,
        phase_label: null,
        completed_items: 2,
        total_items: 3,
        failed_item_keys: ["SHOT-02"],
        error: { code: "PROVIDER_QUALITY_REJECT", message: "镜头2画面缺陷：主体消失超过 2 秒。", retryable: true },
        created_at: nowIso(),
        updated_at: nowIso(),
        finished_at: nowIso(),
      });
      break;
    }

    case "node_stale": {
      // 教案重新批准后，下游三类九套 / 大纲变 stale
      const intro = db.nodeRuns.get(ID.nrIntroOptionsA2);
      if (intro) {
        intro.status = "stale";
        intro.stale_reason = {
          upstream: "lesson_plan",
          message: "教案已更新到 v3，九套方案基于旧版教案生成。",
          changed_at: nowIso(),
        };
      }
      const introState = db.introOptionSets.get(ID.lessonA2);
      if (introState) introState.set.status = "stale";
      const outline = db.nodeRuns.get(ID.nrPptOutlineA2);
      if (outline) {
        outline.status = "stale";
        outline.stale_reason = {
          upstream: "lesson_plan",
          message: "教案已更新，大纲可能不再匹配。",
          changed_at: nowIso(),
        };
      }
      const lesson = db.lessons.get(ID.lessonA2);
      if (lesson) {
        lesson.branches.intro_options = { state: "stale", summary: "内容已变化，建议更新", next_step_key: "intro-options" };
        lesson.branches.ppt = { state: "stale", summary: "内容已变化，建议更新", next_step_key: "ppt-outline" };
      }
      break;
    }

    case "creation_independent": {
      // 独立创作：无包批次可直接编辑生成
      break;
    }

    case "creation_from_package": {
      // 种子已含来自项目包的批次（部分完成）
      break;
    }

    case "save_conflict": {
      // 目标槽位已被占用：把树洞夜景槽位塞入现有素材
      const assetId = uuid(3101);
      db.assets.set(assetId, {
        id: assetId,
        project_id: ID.projAlpha,
        kind: "image",
        title: "树洞夜景（旧版）",
        usage_label: "视频素材",
        source_label: "此前保存",
        lesson_id: ID.lessonA2,
        lesson_title: "认识几分之几",
        slot_key: "video.asset.scene.treehole",
        is_current: true,
        preview_url: null,
        version_no: 1,
        created_at: nowIso(),
      });
      break;
    }

    case "sse_recovery": {
      // tasks.ts 的 sseResponse 依据 scenario 在 ~6s 后断流，
      // 前端应指数退避重连并带 Last-Event-ID 续传。
      const run = db.nodeRuns.get(ID.nrLessonPlanA2);
      if (run) {
        run.status = "running";
        const jobId = uuid(3003);
        run.active_job_id = jobId;
        db.jobs.set(jobId, {
          id: jobId,
          kind: "lesson_plan",
          status: "running",
          title: "教案：生成",
          project_id: ID.projAlpha,
          lesson_id: ID.lessonA2,
          node_run_id: run.id,
          batch_id: null,
          phase_label: "正在生成",
          completed_items: null,
          total_items: null,
          failed_item_keys: [],
          error: null,
          created_at: nowIso(),
          updated_at: nowIso(),
          finished_at: null,
        });
      }
      break;
    }

    case "budget_pause": {
      // projAuto 种子即为暂停等待费用确认
      break;
    }

    case "admin_content_publish": {
      // 简案内容包处于 dry_run，可直接发布；管理员会话
      db.sessionUserId = ID.userContentAdmin;
      break;
    }
  }
  return true;
}

export const scenarioHandlers = [
  http.post(API("/__scenario"), async ({ request }) => {
    const body = (await request.json()) as { scenario?: string; speed_factor?: number; login_as?: string };
    const scenario = body.scenario ?? "default";
    if (!applyScenario(scenario)) {
      return fail(422, "UNKNOWN_SCENARIO", `未知场景：${scenario}`);
    }
    if (body.speed_factor !== undefined) db.speedFactor = body.speed_factor;
    if (body.login_as) {
      const user = db.users.find((u) => u.email === body.login_as);
      if (user) db.sessionUserId = user.id;
    }
    return ok({ scenario: db.scenario, route: SCENARIO_ROUTES[scenario as ScenarioKey] });
  }),

  http.get(API("/__scenario"), () =>
    ok({ scenario: db.scenario, available: SCENARIOS, routes: SCENARIO_ROUTES }),
  ),
];
