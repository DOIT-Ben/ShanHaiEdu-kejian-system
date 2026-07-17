import { http } from "msw";
import { db, emitEvent, nextId, nowIso } from "../db";
import { API, checkIfMatch, fail, idempotent, notFound, ok, requireSession, simulateLatency } from "../http";
import { startJob } from "../engine";
import { nodeTitle } from "../seed";

function projectPayload(project: NonNullable<ReturnType<typeof db.projects.get>>) {
  return {
    id: project.id,
    title: project.title,
    subject: "primary_math" as const,
    grade: project.grade,
    textbook_edition: project.textbook_edition,
    knowledge_point: project.knowledge_point,
    status: project.status,
    automation_mode: project.automation_mode,
    created_at: project.created_at,
    updated_at: project.updated_at,
  };
}

function lessonPayload(lesson: NonNullable<ReturnType<typeof db.lessons.get>>) {
  return {
    id: lesson.id,
    project_id: lesson.project_id,
    position: lesson.position,
    title: lesson.title,
    focus: lesson.focus,
    duration_minutes: lesson.duration_minutes,
    branches: lesson.branches,
    updated_at: lesson.updated_at,
  };
}

function materialPayload(projectId: string) {
  const material = db.materials.get(projectId);
  if (!material) return null;
  return {
    id: material.id,
    project_id: material.project_id,
    status: material.status,
    file_name: material.file_name,
    page_count: material.page_count,
    knowledge_scope: material.knowledge_scope,
    evidence: material.evidence,
    failure_reason: material.failure_reason,
    uploaded_at: material.uploaded_at,
  };
}

function automationPayload(projectId: string) {
  const automation = db.automations.get(projectId);
  if (!automation) return null;
  return {
    state: automation.state,
    paused_reason: automation.paused_reason,
    paused_detail: automation.paused_detail,
    pending_estimate: automation.pending_estimate,
    spent_minor_units: automation.spent_minor_units,
    budget_minor_units: automation.budget_minor_units,
    currency: "CNY",
  };
}

export function nodeRunPayload(run: NonNullable<ReturnType<typeof db.nodeRuns.get>>) {
  return {
    id: run.id,
    node_key: run.node_key,
    status: run.status,
    title: run.title,
    lesson_id: run.lesson_id,
    current_artifact_version_id: run.current_artifact_version_id,
    active_job_id: run.active_job_id,
    skippable: run.skippable,
    stale_reason: run.stale_reason,
    updated_at: run.updated_at,
  };
}

export const projectHandlers = [
  http.get(API("/projects"), async () => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const items = [...db.projects.values()]
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(projectPayload);
    return ok({ items }, { meta: { next_cursor: null } });
  }),

  http.post(API("/projects"), async ({ request }) => {
    await simulateLatency(200);
    const denied = requireSession();
    if (denied) return denied;
    const body = (await request.json()) as {
      title?: string;
      knowledge_point?: string;
      grade?: string | null;
      textbook_edition?: string | null;
      automation_mode?: "manual" | "assisted" | "automatic";
    };
    if (!body.title || !body.knowledge_point) {
      return fail(422, "VALIDATION_FAILED", "项目名称与知识点为必填。", {
        details: {
          field_errors: {
            ...(body.title ? {} : { title: "请输入项目名称" }),
            ...(body.knowledge_point ? {} : { knowledge_point: "请输入知识点" }),
          },
        },
      });
    }
    return idempotent(request, `create-project:${body.title}`, () => {
      const id = nextId();
      const now = nowIso();
      db.projects.set(id, {
        id,
        title: body.title!,
        knowledge_point: body.knowledge_point!,
        grade: body.grade ?? null,
        textbook_edition: body.textbook_edition ?? null,
        status: "draft",
        automation_mode: body.automation_mode ?? "assisted",
        created_at: now,
        updated_at: now,
        etag: 1,
      });
      db.automations.set(id, {
        project_id: id,
        state: "idle",
        paused_reason: null,
        paused_detail: null,
        pending_estimate: null,
        spent_minor_units: 0,
        budget_minor_units: 30000,
      });
      db.deliveries.set(id, { project_id: id, status: "not_ready", package: null });
      emitEvent({
        event_type: "project.created",
        project_id: id,
        resource: { type: "project", id },
      });
      return { data: projectPayload(db.projects.get(id)!), status: 201 };
    });
  }),

  http.get(API("/projects/:projectId"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    return ok(projectPayload(project), { etag: project.etag });
  }),

  http.patch(API("/projects/:projectId"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    const conflict = checkIfMatch(request, project.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { title?: string; automation_mode?: "manual" | "assisted" | "automatic" };
    return idempotent(request, `update-project:${project.id}:${JSON.stringify(body)}`, () => {
      if (body.title) project.title = body.title;
      if (body.automation_mode) project.automation_mode = body.automation_mode;
      project.updated_at = nowIso();
      project.etag += 1;
      emitEvent({
        event_type: "project.updated",
        project_id: project.id,
        resource: { type: "project", id: project.id },
      });
      return { data: projectPayload(project), etag: project.etag };
    });
  }),

  http.get(API("/projects/:projectId/workflow"), async ({ params }) => {
    await simulateLatency(160);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    const lessons = [...db.lessons.values()]
      .filter((l) => l.project_id === project.id)
      .sort((a, b) => a.position - b.position)
      .map(lessonPayload);
    const nodeRuns = [...db.nodeRuns.values()]
      .filter((run) => run.project_id === project.id)
      .map(nodeRunPayload);
    return ok({
      project: projectPayload(project),
      lessons,
      node_runs: nodeRuns,
      material: materialPayload(project.id),
      automation: automationPayload(project.id),
    });
  }),

  // ── 教材 ─────────────────────────────────────────────
  http.post(API("/projects/:projectId/upload-sessions"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    const body = (await request.json()) as { file_name?: string; size_bytes?: number; mime_type?: string };
    if (!body.file_name || !body.size_bytes) {
      return fail(422, "VALIDATION_FAILED", "缺少文件信息。");
    }
    if (body.mime_type !== "application/pdf") {
      return fail(422, "UNSUPPORTED_FILE_TYPE", "目前只支持 PDF 教材。", {
        details: { field_errors: { file: "请上传 PDF 文件" } },
      });
    }
    return idempotent(request, `upload:${project.id}:${body.file_name}`, () => {
      const sessionId = nextId();
      db.materials.set(project.id, {
        id: nextId(),
        project_id: project.id,
        status: "uploading",
        file_name: body.file_name!,
        page_count: null,
        knowledge_scope: null,
        evidence: [],
        failure_reason: null,
        uploaded_at: null,
      });
      return {
        data: {
          upload_session_id: sessionId,
          upload_url: `/api/v2/__mock-upload/${sessionId}`,
          required_headers: { "Content-Type": "application/pdf" },
          expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        },
        status: 201,
      };
    });
  }),

  // mock 直传端点（真实实现直传对象存储）
  http.put(API("/__mock-upload/:sessionId"), async () => {
    await simulateLatency(300);
    return new Response(null, { status: 200 });
  }),

  http.post(API("/upload-sessions/:sessionId/complete"), async ({ request }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    // 找到最近 uploading 的教材（mock 简化：单会话）
    const material = [...db.materials.values()].find((m) => m.status === "uploading");
    if (!material) return notFound("上传会话");
    const project = db.projects.get(material.project_id)!;
    const job = startJob({
      kind: "material_parse",
      title: `解析教材：${material.file_name}`,
      projectId: project.id,
      phaseMs: [700, 2200],
      onComplete: () => {
        material.status = "parsed";
        material.page_count = 6;
        material.knowledge_scope = `教材第 90–93 页：${project.knowledge_point}。`;
        material.evidence = [
          { page_no: 90, summary: "情境引入与核心问题" },
          { page_no: 91, summary: "概念建构与示例" },
          { page_no: 92, summary: "基础练习" },
          { page_no: 93, summary: "拓展与生活联系" },
        ];
        material.uploaded_at = nowIso();
        emitEvent({
          event_type: "material.parsed",
          project_id: project.id,
          resource: { type: "material", id: material.id },
        });
      },
    });
    material.status = "scanning";
    setTimeout(() => {
      if (material.status === "scanning") material.status = "parsing";
    }, 400 * db.speedFactor);
    void request;
    return ok(
      { job_id: job.id, status: "queued", events_url: `/api/v2/generation-jobs/${job.id}/events/stream` },
      { status: 202 },
    );
  }),

  http.get(API("/projects/:projectId/material"), async ({ params }) => {
    await simulateLatency(90);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    return ok({ material: materialPayload(project.id) });
  }),

  http.post(API("/projects/:projectId/material/confirm-scope"), async ({ params, request }) => {
    await simulateLatency(120);
    const denied = requireSession();
    if (denied) return denied;
    const project = db.projects.get(params.projectId as string);
    if (!project) return notFound("项目");
    const material = db.materials.get(project.id);
    if (!material || material.status !== "parsed") {
      return fail(409, "MATERIAL_NOT_PARSED", "教材尚未完成解析，无法确认范围。");
    }
    return idempotent(request, `confirm-scope:${project.id}`, () => {
      material.status = "scope_confirmed";
      project.status = "active";
      project.updated_at = nowIso();
      project.etag += 1;
      if (!db.divisions.get(project.id)) {
        db.divisions.set(project.id, {
          project_id: project.id,
          status: "not_ready",
          source_evidence_note: null,
          entries: [],
          etag: 1,
        });
      }
      emitEvent({
        event_type: "material.scope_confirmed",
        project_id: project.id,
        resource: { type: "material", id: material.id },
      });
      // 范围确认后系统自动生成课时划分（契约无独立 generate 端点）
      startJob({
        kind: "lesson_division",
        title: `生成课时划分：${project.title}`,
        projectId: project.id,
        phaseMs: [600, 1800],
        onComplete: () => {
          const division = db.divisions.get(project.id)!;
          division.status = "review_required";
          division.source_evidence_note = "依据教材证据自动划分，可增删与排序。";
          division.entries = [
            { entry_id: nextId(), position: 1, title: `${project.knowledge_point}（一）`, focus: "概念初建与操作体验", duration_minutes: 40, lesson_id: null },
            { entry_id: nextId(), position: 2, title: `${project.knowledge_point}（二）`, focus: "深化理解与表达", duration_minutes: 40, lesson_id: null },
          ];
          division.etag += 1;
          emitEvent({
            event_type: "lesson_division.generated",
            project_id: project.id,
            resource: { type: "lesson_division", id: project.id },
          });
        },
      });
      return { data: { material: materialPayload(project.id) } };
    });
  }),

  // ── 课时划分 ─────────────────────────────────────────
  http.get(API("/projects/:projectId/lesson-division"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    if (!db.projects.get(projectId)) return notFound("项目");
    const division = db.divisions.get(projectId);
    if (!division) {
      return ok({ status: "not_ready", source_evidence_note: null, entries: [] }, { etag: 0 });
    }
    return ok(
      {
        status: division.status,
        source_evidence_note: division.source_evidence_note,
        entries: division.entries,
      },
      { etag: division.etag },
    );
  }),

  http.put(API("/projects/:projectId/lesson-division"), async ({ params, request }) => {
    await simulateLatency(150);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    const division = db.divisions.get(projectId);
    if (!division) return notFound("课时划分");
    if (division.status === "approved") {
      return fail(409, "DIVISION_APPROVED", "课时划分已批准，如需调整请在课时列表中操作。");
    }
    const conflict = checkIfMatch(request, division.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as {
      entries?: { entry_id?: string | null; title: string; focus: string; duration_minutes?: number | null }[];
    };
    if (!body.entries?.length) {
      return fail(422, "VALIDATION_FAILED", "至少保留一个课时。");
    }
    division.entries = body.entries.map((entry, index) => ({
      entry_id: entry.entry_id ?? nextId(),
      position: index + 1,
      title: entry.title,
      focus: entry.focus,
      duration_minutes: entry.duration_minutes ?? 40,
      lesson_id: division.entries.find((e) => e.entry_id === entry.entry_id)?.lesson_id ?? null,
    }));
    division.status = "draft";
    division.etag += 1;
    return ok(
      { status: division.status, source_evidence_note: division.source_evidence_note, entries: division.entries },
      { etag: division.etag },
    );
  }),

  http.post(API("/projects/:projectId/lesson-division/approve"), async ({ params, request }) => {
    await simulateLatency(180);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    const division = db.divisions.get(projectId);
    if (!division) return notFound("课时划分");
    if (!division.entries.length) {
      return fail(409, "DIVISION_EMPTY", "尚无课时可批准。");
    }
    return idempotent(request, `approve-division:${projectId}`, () => {
      division.status = "approved";
      division.etag += 1;
      // 为每个条目创建课时
      division.entries.forEach((entry) => {
        if (entry.lesson_id) return;
        const lessonId = nextId();
        entry.lesson_id = lessonId;
        db.lessons.set(lessonId, {
          id: lessonId,
          project_id: projectId,
          position: entry.position,
          title: entry.title,
          focus: entry.focus,
          duration_minutes: entry.duration_minutes,
          branches: {
            lesson_plan: { state: "not_ready", summary: "等待生成", next_step_key: "lesson-plan" },
            intro_options: { state: "not_ready", summary: null, next_step_key: null },
            ppt: { state: "disabled", summary: "尚未启用", next_step_key: null },
            video: { state: "disabled", summary: "尚未启用", next_step_key: null },
          },
          updated_at: nowIso(),
          etag: 1,
        });
      });
      emitEvent({
        event_type: "lesson_division.approved",
        project_id: projectId,
        resource: { type: "lesson_division", id: projectId },
      });
      return {
        data: { status: division.status, source_evidence_note: division.source_evidence_note, entries: division.entries },
        etag: division.etag,
      };
    });
  }),

  // ── 课时 ─────────────────────────────────────────────
  http.get(API("/projects/:projectId/lessons"), async ({ params }) => {
    await simulateLatency(100);
    const denied = requireSession();
    if (denied) return denied;
    const projectId = params.projectId as string;
    if (!db.projects.get(projectId)) return notFound("项目");
    const items = [...db.lessons.values()]
      .filter((l) => l.project_id === projectId)
      .sort((a, b) => a.position - b.position)
      .map(lessonPayload);
    return ok({ items });
  }),

  http.get(API("/lessons/:lessonId"), async ({ params }) => {
    await simulateLatency(90);
    const denied = requireSession();
    if (denied) return denied;
    const lesson = db.lessons.get(params.lessonId as string);
    if (!lesson) return notFound("课时");
    return ok(lessonPayload(lesson), { etag: lesson.etag });
  }),

  http.patch(API("/lessons/:lessonId"), async ({ params, request }) => {
    await simulateLatency(140);
    const denied = requireSession();
    if (denied) return denied;
    const lesson = db.lessons.get(params.lessonId as string);
    if (!lesson) return notFound("课时");
    const conflict = checkIfMatch(request, lesson.etag);
    if (conflict) return conflict;
    const body = (await request.json()) as { ppt_enabled?: boolean; video_enabled?: boolean; intro_enabled?: boolean };
    return idempotent(request, `lesson-branch:${lesson.id}:${JSON.stringify(body)}`, () => {
      if (body.ppt_enabled !== undefined) {
        lesson.branches.ppt = body.ppt_enabled
          ? { state: "not_ready", summary: "等待教案批准", next_step_key: "ppt-outline" }
          : { state: "disabled", summary: "已停用", next_step_key: null };
      }
      if (body.video_enabled !== undefined) {
        lesson.branches.video = body.video_enabled
          ? { state: "not_ready", summary: "等待选择导入方案", next_step_key: "intro-selection" }
          : { state: "disabled", summary: "已停用", next_step_key: null };
      }
      if (body.intro_enabled !== undefined) {
        lesson.branches.intro_options = body.intro_enabled
          ? { state: "not_ready", summary: null, next_step_key: "intro-options" }
          : { state: "disabled", summary: "本课时不需要导入设计", next_step_key: null };
      }
      lesson.etag += 1;
      lesson.updated_at = nowIso();
      // 同步节点 disabled 状态
      for (const run of db.nodeRuns.values()) {
        if (run.lesson_id !== lesson.id) continue;
        if (run.node_key.startsWith("ppt") && body.ppt_enabled !== undefined) {
          run.status = body.ppt_enabled ? (run.node_key === "ppt_outline" ? "ready" : "not_ready") : "disabled";
        }
        if (run.node_key.startsWith("video") && body.video_enabled !== undefined) {
          run.status = body.video_enabled ? (run.node_key === "video_script" ? "ready" : "not_ready") : "disabled";
        }
      }
      emitEvent({
        event_type: "lesson.branches_changed",
        project_id: lesson.project_id,
        resource: { type: "lesson", id: lesson.id },
      });
      return { data: lessonPayload(lesson), etag: lesson.etag };
    });
  }),

  http.get(API("/lessons/:lessonId/node-runs"), async ({ params }) => {
    await simulateLatency(110);
    const denied = requireSession();
    if (denied) return denied;
    const lessonId = params.lessonId as string;
    const lesson = db.lessons.get(lessonId);
    if (!lesson) return notFound("课时");
    const { ensureLessonNodeRuns } = await import("../seed");
    ensureLessonNodeRuns(lessonId);
    const items = [...db.nodeRuns.values()]
      .filter((run) => run.lesson_id === lessonId)
      .map(nodeRunPayload);
    return ok({ items });
  }),
];

export { projectPayload, lessonPayload, materialPayload, automationPayload, nodeTitle };
