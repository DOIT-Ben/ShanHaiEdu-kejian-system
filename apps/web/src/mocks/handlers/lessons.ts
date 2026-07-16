import { http } from "msw";
import type { Lesson, NodeWorkspace, UpstreamReference } from "@/shared/api/types";
import { getNodeDef, LESSON_NODES } from "@/entities/workflow/nodes";
import { getDb, type LessonState, type MockDb, type ProjectState } from "../db";
import { publishEvent } from "../events";
import { cancelTask } from "../engine";
import { api, fail, guard, ok, simulateLatency } from "./http";

export function findLesson(db: MockDb, lessonId: string): { project: ProjectState; lessonState: LessonState } | null {
  for (const project of db.projects.values()) {
    const lessonState = project.lessons.find((l) => l.lesson.lesson_id === lessonId);
    if (lessonState) return { project, lessonState };
  }
  return null;
}

/** 课时阶段摘要（列表页用）。 */
function withStageSummary(lessonState: LessonState): Lesson {
  const status = (key: string) => lessonState.nodes.get(key)?.summary.status ?? "locked";
  const worst = (keys: string[]) => {
    const order = ["failed", "blocked", "stale", "revision_required", "needs_review", "running", "queued", "ready", "locked", "cancelled", "approved", "skipped"];
    const statuses = keys.map(status);
    if (statuses.every((s) => s === "approved" || s === "skipped")) return statuses.includes("approved") ? "approved" : "skipped";
    return [...statuses].sort((a, b) => order.indexOf(a) - order.indexOf(b))[0];
  };
  return {
    ...lessonState.lesson,
    stage_summary: {
      lesson_plan: status("lesson_plan"),
      intro_design: status("intro_design"),
      ppt: worst(["ppt_outline", "ppt_pages", "ppt_assets", "ppt_preview", "ppt_export"]),
      video: worst([
        "video_master_script",
        "video_visual_direction",
        "video_master_image",
        "video_rough_storyboard",
        "video_image_assets",
        "video_fine_storyboard",
        "video_shot_prompts",
        "video_clips",
        "video_audio_subtitle",
        "video_final_cut",
      ]),
      delivery: status("delivery"),
    },
  };
}

export function buildNodeWorkspace(lessonState: LessonState, nodeKey: string): NodeWorkspace | null {
  const node = lessonState.nodes.get(nodeKey);
  const def = getNodeDef(nodeKey);
  if (!node || !def) return null;
  const upstream: UpstreamReference[] = def.dependsOn.map((depKey) => {
    const dep = lessonState.nodes.get(depKey);
    const depDef = getNodeDef(depKey);
    const approved = dep?.artifactVersions.find((v) => v.status === "approved") ?? dep?.artifactVersions[0];
    return {
      node_key: depKey,
      title: depDef?.title ?? depKey,
      status: dep?.summary.status ?? "locked",
      artifact_version_id: approved?.artifact_version_id ?? null,
      version_number: approved?.version_number ?? null,
      stale: dep?.summary.status === "stale",
    };
  });
  return {
    node: node.summary,
    description: node.description,
    capability: def.capability,
    input_schema: node.inputSchema,
    input_values: node.inputValues,
    input_row_version: node.inputRowVersion,
    draft_content: node.draftContent,
    draft_row_version: node.draftRowVersion,
    output_renderer: def.rendererKey,
    upstream_references: upstream,
    selected_asset_ids: node.selectedAssetIds,
    prompt_versions: node.promptVersions,
    artifact_versions: node.artifactVersions,
    validation_results: node.validationResults,
    active_task_id: node.activeTaskId,
  };
}

export const lessonHandlers = [
  http.get(api("/projects/:projectId/lessons"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    return ok(state.lessons.map(withStageSummary));
  }),

  http.get(api("/lessons/:lessonId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findLesson(getDb(), String(params.lessonId));
    if (!found) return fail(404, "NOT_FOUND", "课时不存在或不可访问。");
    return ok(withStageSummary(found.lessonState));
  }),

  http.get(api("/lessons/:lessonId/workspace"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findLesson(getDb(), String(params.lessonId));
    if (!found) return fail(404, "NOT_FOUND", "课时不存在或不可访问。");
    const { lessonState, project } = found;
    const outputScope = project.project.output_scope ?? { ppt: true, video: true };
    const nodes = LESSON_NODES.filter((def) => {
      if (!outputScope.ppt && def.group === "PPT") return false;
      if (!outputScope.video && def.group === "视频") return false;
      return true;
    }).map((def) => lessonState.nodes.get(def.key)?.summary).filter((n) => n !== undefined);
    return ok({
      lesson: withStageSummary(lessonState),
      nodes,
      current_node_key: lessonState.currentNodeKey,
    });
  }),

  http.get(api("/lessons/:lessonId/nodes/:nodeKey"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findLesson(getDb(), String(params.lessonId));
    if (!found) return fail(404, "NOT_FOUND", "课时不存在或不可访问。");
    const workspace = buildNodeWorkspace(found.lessonState, String(params.nodeKey));
    if (!workspace) return fail(404, "NOT_FOUND", "节点不存在。");
    return ok(workspace);
  }),

  http.patch(api("/lessons/:lessonId/nodes/:nodeKey/inputs"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const found = findLesson(getDb(), String(params.lessonId));
    const node = found?.lessonState.nodes.get(String(params.nodeKey));
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const body = (await request.json()) as { input_values?: Record<string, unknown>; selected_asset_ids?: string[]; row_version?: number };
    if (Number(body.row_version) !== node.inputRowVersion) {
      return fail(409, "VERSION_CONFLICT", "节点输入已在其他位置被修改。", { details: { server_row_version: node.inputRowVersion } });
    }
    if (body.input_values) node.inputValues = body.input_values;
    if (body.selected_asset_ids) node.selectedAssetIds = body.selected_asset_ids;
    node.inputRowVersion += 1;
    return ok(buildNodeWorkspace(found.lessonState, String(params.nodeKey)));
  }),

  http.patch(api("/lessons/:lessonId/nodes/:nodeKey/draft"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const found = findLesson(getDb(), String(params.lessonId));
    const node = found?.lessonState.nodes.get(String(params.nodeKey));
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const body = (await request.json()) as { content?: Record<string, unknown>; row_version?: number };
    if (Number(body.row_version) !== node.draftRowVersion) {
      return fail(409, "VERSION_CONFLICT", "草稿已在其他位置被修改。", { details: { server_row_version: node.draftRowVersion } });
    }
    node.draftContent = body.content ?? null;
    node.draftRowVersion += 1;
    return ok({ row_version: node.draftRowVersion, saved_at: new Date().toISOString() });
  }),

  http.post(api("/lessons/:lessonId/nodes/:nodeKey/transitions"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const nodeKey = String(params.nodeKey);
    const node = found?.lessonState.nodes.get(nodeKey);
    if (!found || !node) return fail(404, "NOT_FOUND", "节点不存在。");
    const def = getNodeDef(nodeKey);
    const body = (await request.json()) as { action?: string; reason?: string };
    const projectId = found.project.project.project_id;
    const lessonId = found.lessonState.lesson.lesson_id;

    switch (body.action) {
      case "skip": {
        if (!def?.skippable) return fail(409, "NOT_SKIPPABLE", "该步骤不允许跳过。");
        node.summary.status = "skipped";
        node.summary.blocker_message = null;
        publishEvent({ event_type: "node.status_changed", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { status: "skipped" } });
        break;
      }
      case "restore": {
        const depsSatisfied = (def?.dependsOn ?? []).every((dep) => {
          const status = found.lessonState.nodes.get(dep)?.summary.status;
          return status === "approved" || status === "skipped";
        });
        node.summary.status = node.artifactVersions.length > 0 ? "needs_review" : depsSatisfied ? "ready" : "locked";
        node.summary.blocker_message = node.summary.status === "locked" ? "等待上游步骤完成" : null;
        publishEvent({ event_type: "node.status_changed", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { status: node.summary.status } });
        break;
      }
      case "pause": {
        if (node.activeTaskId) {
          cancelTask(node.activeTaskId);
          node.activeTaskId = null;
        }
        break;
      }
      case "resume": {
        // 恢复：把失败/取消节点重置为可开始
        if (node.summary.status === "failed" || node.summary.status === "cancelled") {
          node.summary.status = node.artifactVersions.length > 0 ? "needs_review" : "ready";
          publishEvent({ event_type: "node.status_changed", project_id: projectId, lesson_id: lessonId, node_key: nodeKey, task_id: null, payload: { status: node.summary.status } });
        }
        break;
      }
      default:
        return fail(422, "INVALID_ACTION", "不支持的节点操作。");
    }
    return ok(buildNodeWorkspace(found.lessonState, nodeKey));
  }),

  http.get(api("/lessons/:lessonId/nodes/:nodeKey/model-options"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const found = findLesson(db, String(params.lessonId));
    const def = getNodeDef(String(params.nodeKey));
    if (!found || !def) return fail(404, "NOT_FOUND", "节点不存在。");
    const capability = def.capability;
    const route = db.routes.find((r) => r.capability === capability && r.enabled);
    const advancedModels = db.models
      .filter((m) => capability && m.capabilities.includes(capability) && m.enabled)
      .map((m) => ({ model_id: m.model_id, business_name: m.business_name, provider_name: m.provider_name ?? "", upstream_name: null }));
    return ok({
      profiles: [
        { profile: "recommended" as const, business_name: "推荐", description: "按平台路由策略自动选择，质量与成本均衡。", default_candidate_count: 1 },
        { profile: "quality" as const, business_name: "质量优先", description: "使用能力最强的模型，费用更高。", default_candidate_count: 2 },
        { profile: "economy" as const, business_name: "经济", description: "控制费用，适合初稿。", default_candidate_count: 1 },
        { profile: "fast_draft" as const, business_name: "快速草稿", description: "最快返回，用于快速看方向。", default_candidate_count: 1 },
      ],
      advanced_models: advancedModels,
      allow_advanced: true,
      allow_fallback: route?.allow_cross_provider_fallback ?? false,
      parameter_bounds: route?.parameter_bounds ?? {},
    });
  }),
];
