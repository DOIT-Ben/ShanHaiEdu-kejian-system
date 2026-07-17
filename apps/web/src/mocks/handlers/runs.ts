import { http } from "msw";
import { db, emitEvent, nextId, nowIso, touchLesson } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { startJob, produceResults } from "../engine";
import { nodeRunPayload } from "./projects";
import { lessonPlanDefinition, lessonPlanContent, lessonPlanWarning } from "../fixtures";

/**
 * 节点运行、提示词、作品版本与审批。
 * 节点状态 / 任务状态 / 批准状态分别推进，不用一个字段控制全部界面。
 */

function artifactPayload(version: NonNullable<ReturnType<typeof db.artifactVersions.get>>) {
  return {
    id: version.id,
    node_run_id: version.node_run_id,
    kind: version.kind,
    review_status: version.review_status,
    version_no: version.version_no,
    is_current: version.is_current,
    content: version.content,
    content_definition_version_id: version.content_definition_version_id,
    validation_issues: version.validation_issues,
    source: version.source,
    created_at: version.created_at,
    approved_at: version.approved_at,
    approval_note: version.approval_note,
  };
}

function refreshLessonPlanBranch(lessonId: string, state: "review_required" | "approved") {
  const lesson = db.lessons.get(lessonId);
  if (!lesson) return;
  lesson.branches.lesson_plan =
    state === "approved"
      ? { state: "approved", summary: "教案已批准", next_step_key: null }
      : { state: "review_required", summary: "教案等待你确认", next_step_key: "lesson-plan-confirm" };
  // 教案批准解锁 PPT 大纲
  if (state === "approved" && lesson.branches.ppt.state !== "disabled") {
    for (const run of db.nodeRuns.values()) {
      if (run.lesson_id === lessonId && run.node_key === "ppt_outline" && run.status === "not_ready") {
        run.status = "ready";
        run.updated_at = nowIso();
      }
    }
    if (lesson.branches.ppt.state === "not_ready") {
      lesson.branches.ppt = { state: "in_progress", summary: "可以开始安排页面", next_step_key: "ppt-outline" };
    }
  }
  touchLesson(lessonId);
}

export const nodeRunHandlers = [
  http.get(API("/node-runs/:nodeRunId"), async ({ params }) => {
    await simulateLatency(110);
    const denied = requireSession();
    if (denied) return denied;
    const run = db.nodeRuns.get(params.nodeRunId as string);
    if (!run) return notFound("步骤");
    const current = run.current_artifact_version_id
      ? db.artifactVersions.get(run.current_artifact_version_id) ?? null
      : null;
    const activeJob = run.active_job_id ? db.jobs.get(run.active_job_id) ?? null : null;
    const versions = [...db.artifactVersions.values()]
      .filter((v) => v.node_run_id === run.id)
      .sort((a, b) => b.version_no - a.version_no)
      .map((v) => ({
        id: v.id,
        version_no: v.version_no,
        review_status: v.review_status,
        source: v.source,
        created_at: v.created_at,
      }));
    return ok({
      node_run: nodeRunPayload(run),
      artifact_version: current ? artifactPayload(current) : null,
      active_job: activeJob
        ? (() => {
            const { plan: _plan, ...job } = activeJob;
            return job;
          })()
        : null,
      versions,
    });
  }),

  http.get(API("/node-runs/:nodeRunId/prompt-preview"), async ({ params }) => {
    await simulateLatency(90);
    const denied = requireSession();
    if (denied) return denied;
    const prompt = db.prompts.get(params.nodeRunId as string);
    if (!prompt) return notFound("生成指令");
    return ok(
      {
        editable_prompt: prompt.editable_prompt,
        prompt_revision_id: prompt.prompt_revision_id,
        locked_layers: prompt.locked_layers,
        context_summary: prompt.context_summary,
        schema: null,
      },
      { etag: prompt.etag },
    );
  }),

  http.put(API("/node-runs/:nodeRunId/prompt"), async ({ params, request }) => {
    await simulateLatency(130);
    const denied = requireSession();
    if (denied) return denied;
    const prompt = db.prompts.get(params.nodeRunId as string);
    if (!prompt) return notFound("生成指令");
    const conflict = checkIfMatch(request, prompt.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { editable_prompt?: string };
    if (!body.editable_prompt?.trim()) {
      return fail(422, "VALIDATION_FAILED", "生成指令不能为空。", {
        details: { field_errors: { editable_prompt: "请输入生成指令" } },
      });
    }
    prompt.editable_prompt = body.editable_prompt;
    prompt.prompt_revision_id = nextId();
    prompt.etag += 1;
    db.auditEvents.unshift({
      id: nextId(),
      actor_name: db.users.find((u) => u.id === db.sessionUserId)?.name ?? "未知用户",
      action: "prompt.edit",
      resource_label: `${db.nodeRuns.get(params.nodeRunId as string)?.title ?? "节点"}生成指令`,
      detail: "人工修改生成指令",
      occurred_at: nowIso(),
    });
    return ok(
      { prompt_revision_id: prompt.prompt_revision_id, created_at: nowIso() },
      { etag: prompt.etag },
    );
  }),

  http.post(API("/node-runs/:nodeRunId/start"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const run = db.nodeRuns.get(params.nodeRunId as string);
    if (!run) return notFound("步骤");
    if (run.status === "queued" || run.status === "running") {
      return fail(409, "NODE_BUSY", "当前步骤已在生成中。", { retryable: false });
    }
    if (run.status === "disabled" || run.status === "not_ready") {
      return fail(409, "NODE_NOT_READY", "前置步骤尚未完成，暂时不能开始。");
    }
    // 全自动项目的预算暂停
    const automation = db.automations.get(run.project_id);
    if (automation?.state === "paused" && automation.paused_reason === "budget_confirmation_required") {
      return fail(403, "BUDGET_AUTHORIZATION_REQUIRED", "自动执行等待费用确认，请先确认预算。", {
        details: {
          pending_estimate: automation.pending_estimate,
        },
      });
    }

    return idempotent(request, `start:${run.id}`, () => {
      const job = startJob({
        kind: run.node_key,
        title: `${run.title}：生成`,
        projectId: run.project_id,
        lessonId: run.lesson_id,
        nodeRunId: run.id,
        phaseMs: [800, 2600],
        onComplete: () => {
          completeNodeGeneration(run.id);
        },
      });
      return {
        data: { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),

  http.post(API("/node-runs/:nodeRunId/transitions"), async ({ params, request }) => {
    await simulateLatency(130);
    const denied = requireSession();
    if (denied) return denied;
    const run = db.nodeRuns.get(params.nodeRunId as string);
    if (!run) return notFound("步骤");
    const body = (await request.json()) as {
      action?: "skip" | "resume" | "keep_current_version" | "acknowledge_stale";
      reason?: string | null;
    };
    return idempotent(request, `transition:${run.id}:${body.action}`, () => {
      switch (body.action) {
        case "skip": {
          if (!run.skippable) {
            return fail(409, "NODE_NOT_SKIPPABLE", "该步骤不可跳过。");
          }
          run.status = "skipped";
          break;
        }
        case "resume": {
          if (run.status === "paused" || run.status === "skipped" || run.status === "cancelled") {
            run.status = run.current_artifact_version_id ? "review_required" : "ready";
          }
          break;
        }
        case "keep_current_version":
        case "acknowledge_stale": {
          if (run.status === "stale") {
            run.status = run.current_artifact_version_id ? "approved" : "ready";
            run.stale_reason = null;
          }
          break;
        }
        default:
          return fail(422, "VALIDATION_FAILED", "未知的操作。");
      }
      run.updated_at = nowIso();
      emitEvent({
        event_type: "node_run.status_changed",
        project_id: run.project_id,
        resource: { type: "node_run", id: run.id },
        payload: { status: run.status },
      });
      return { data: nodeRunPayload(run) };
    });
  }),

  http.get(API("/node-runs/:nodeRunId/results"), async ({ params, request }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const nodeRunId = params.nodeRunId as string;
    if (!db.nodeRuns.get(nodeRunId)) return notFound("步骤");
    const url = new URL(request.url);
    const itemKey = url.searchParams.get("item_key");
    const items = [...db.results.values()]
      .filter((r) => r.node_run_id === nodeRunId && (!itemKey || r.item_key === itemKey))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    return ok({ items });
  }),

  // ── 作品版本 ────────────────────────────────────────
  http.get(API("/artifact-versions/:versionId"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const version = db.artifactVersions.get(params.versionId as string);
    if (!version) return notFound("作品版本");
    return ok(artifactPayload(version), { etag: version.etag });
  }),

  http.put(API("/artifact-versions/:versionId/content"), async ({ params, request }) => {
    await simulateLatency(160);
    const denied = requireSession();
    if (denied) return denied;
    const version = db.artifactVersions.get(params.versionId as string);
    if (!version) return notFound("作品版本");
    if (version.review_status === "approved" || version.review_status === "superseded") {
      return fail(409, "VERSION_IMMUTABLE", "已批准版本不可修改；请生成新版本。");
    }
    const conflict = checkIfMatch(request, version.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { content?: Record<string, unknown> };
    if (!body.content) return fail(422, "VALIDATION_FAILED", "缺少内容。");
    version.content = body.content;
    version.source = "teacher_edited";
    version.etag += 1;
    emitEvent({
      event_type: "artifact_version.updated",
      project_id: db.nodeRuns.get(version.node_run_id)?.project_id ?? null,
      resource: { type: "artifact_version", id: version.id },
    });
    return ok(artifactPayload(version), { etag: version.etag });
  }),

  http.post(API("/artifact-versions/:versionId/approve"), async ({ params, request }) => {
    await simulateLatency(200);
    const denied = requireSession();
    if (denied) return denied;
    const version = db.artifactVersions.get(params.versionId as string);
    if (!version) return notFound("作品版本");
    const run = db.nodeRuns.get(version.node_run_id);
    if (!run) return notFound("步骤");
    const body = (await request.json().catch(() => ({}))) as {
      note?: string | null;
      acknowledged_warning_keys?: string[];
      acknowledgement_note?: string | null;
    } | null;

    const warnings = version.validation_issues.filter((issue) => issue.severity === "warning");
    const acknowledged = new Set(body?.acknowledged_warning_keys ?? []);
    const unacknowledged = warnings.filter((w) => !acknowledged.has(w.key));
    if (unacknowledged.length > 0) {
      return fail(409, "WARNINGS_UNACKNOWLEDGED", "存在未确认的校验警告，请逐条确认后批准。", {
        details: {
          warnings: unacknowledged.map((w) => ({ key: w.key, message: w.message })),
        },
      });
    }
    if (warnings.length > 0 && !body?.acknowledgement_note?.trim()) {
      return fail(422, "ACKNOWLEDGEMENT_NOTE_REQUIRED", "确认校验警告时必须填写说明。", {
        details: { field_errors: { acknowledgement_note: "请填写确认说明" } },
      });
    }

    return idempotent(request, `approve:${version.id}`, () => {
      version.review_status = "approved";
      version.approved_at = nowIso();
      version.approval_note = body?.note ?? body?.acknowledgement_note ?? null;
      version.etag += 1;
      run.status = "approved";
      run.updated_at = nowIso();
      if (run.node_key === "lesson_plan" && run.lesson_id) {
        refreshLessonPlanBranch(run.lesson_id, "approved");
      }
      db.auditEvents.unshift({
        id: nextId(),
        actor_name: db.users.find((u) => u.id === db.sessionUserId)?.name ?? "未知用户",
        action: "artifact.approve",
        resource_label: `${run.title} v${version.version_no}`,
        detail: version.approval_note,
        occurred_at: nowIso(),
      });
      emitEvent({
        event_type: "node_run.status_changed",
        project_id: run.project_id,
        resource: { type: "node_run", id: run.id },
        payload: { status: run.status },
      });
      return { data: artifactPayload(version), etag: version.etag };
    });
  }),

  http.post(API("/artifact-versions/:versionId/request-changes"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const version = db.artifactVersions.get(params.versionId as string);
    if (!version) return notFound("作品版本");
    const run = db.nodeRuns.get(version.node_run_id);
    if (!run) return notFound("步骤");
    const body = (await request.json()) as { instruction?: string; scope_keys?: string[] };
    if (!body.instruction?.trim()) {
      return fail(422, "VALIDATION_FAILED", "请填写修改要求。", {
        details: { field_errors: { instruction: "请说明需要修改什么" } },
      });
    }
    return idempotent(request, `request-changes:${version.id}:${body.instruction}`, () => {
      const job = startJob({
        kind: `${run.node_key}_revision`,
        title: `${run.title}：局部返修`,
        projectId: run.project_id,
        lessonId: run.lesson_id,
        nodeRunId: run.id,
        phaseMs: [700, 2200],
        onComplete: () => {
          // 生成新版本（旧版本 superseded）
          version.review_status = "superseded";
          version.is_current = false;
          const newId = nextId();
          db.artifactVersions.set(newId, {
            ...version,
            id: newId,
            review_status: "review_required",
            version_no: version.version_no + 1,
            is_current: true,
            content: version.content,
            source: "generated",
            created_at: nowIso(),
            approved_at: null,
            approval_note: null,
            etag: 1,
          });
          run.current_artifact_version_id = newId;
          run.status = "review_required";
          run.updated_at = nowIso();
          emitEvent({
            event_type: "node_run.status_changed",
            project_id: run.project_id,
            resource: { type: "node_run", id: run.id },
            payload: { status: run.status },
          });
        },
      });
      return {
        data: { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
        status: 202,
      };
    });
  }),
];

/** 节点生成完成时产出对应作品/候选（按 node_key 分派）。 */
export function completeNodeGeneration(nodeRunId: string): void {
  const run = db.nodeRuns.get(nodeRunId);
  if (!run) return;

  const finishWithVersion = (kind: string, content: Record<string, unknown>, issues = [] as typeof lessonPlanWarning[]) => {
    const previous = run.current_artifact_version_id
      ? db.artifactVersions.get(run.current_artifact_version_id)
      : null;
    if (previous) {
      previous.review_status = "superseded";
      previous.is_current = false;
    }
    const id = nextId();
    db.artifactVersions.set(id, {
      id,
      node_run_id: run.id,
      kind,
      review_status: "review_required",
      version_no: (previous?.version_no ?? 0) + 1,
      is_current: true,
      content,
      content_definition_version_id: kind === "lesson_plan" ? previous?.content_definition_version_id ?? null : null,
      validation_issues: issues,
      source: "generated",
      created_at: nowIso(),
      approved_at: null,
      approval_note: null,
      etag: 1,
    });
    run.current_artifact_version_id = id;
    run.status = "review_required";
    run.updated_at = nowIso();
  };

  switch (run.node_key) {
    case "lesson_plan": {
      finishWithVersion(
        "lesson_plan",
        { definition: lessonPlanDefinition, data: lessonPlanContent },
        [lessonPlanWarning],
      );
      if (run.lesson_id) refreshLessonPlanBranch(run.lesson_id, "review_required");
      break;
    }
    case "ppt_cover": {
      produceResults({
        nodeRunId: run.id,
        itemKey: "cover",
        mediaType: "image",
        count: 3,
        labelPrefix: "封面",
        tone: "#2449d8",
      });
      run.status = "review_required";
      run.updated_at = nowIso();
      break;
    }
    default: {
      run.status = "review_required";
      run.updated_at = nowIso();
      break;
    }
  }
  emitEvent({
    event_type: "node_run.status_changed",
    project_id: run.project_id,
    resource: { type: "node_run", id: run.id },
    payload: { status: run.status },
  });
}
