import { http } from "msw";
import type { Project } from "@/shared/api/types";
import { getDb, minutesAgo, nextId } from "../db";
import { publishEvent } from "../events";
import { startTask } from "../engine";
import { buildDivisionContent, buildEvidenceContent } from "../fixtures/content";
import { makeArtifact, makeFreshLessonState } from "../fixtures/projects";
import { makeFileObject } from "../fixtures/files";
import type { DivisionContent } from "@/entities/content";
import { api, fail, guard, ok, paginate, simulateLatency } from "./http";

export const projectHandlers = [
  // ---------- 项目列表 / 创建 ----------
  http.get(api("/projects"), async ({ request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const db = getDb();
    await simulateLatency(Boolean(db.flags.slowProjectList));
    const url = new URL(request.url);
    const status = url.searchParams.get("status");
    const keyword = url.searchParams.get("keyword")?.trim();
    const sort = url.searchParams.get("sort") ?? "updated_desc";
    const pageSize = Number.parseInt(url.searchParams.get("page_size") ?? "30", 10);

    let items = [...db.projects.values()].map((p) => p.project);
    if (status) items = items.filter((p) => p.status === status);
    else items = items.filter((p) => p.status !== "archived");
    if (keyword) items = items.filter((p) => p.name.includes(keyword));
    items.sort((a, b) => {
      if (sort === "name_asc") return a.name.localeCompare(b.name, "zh-CN");
      if (sort === "created_desc") return (b.created_at ?? "").localeCompare(a.created_at ?? "");
      return b.updated_at.localeCompare(a.updated_at);
    });
    const { page, nextCursor } = paginate(items, url.searchParams.get("cursor"), pageSize);
    return ok(page, { meta: { next_cursor: nextCursor } });
  }),

  http.post(api("/projects"), async ({ request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const idempotencyKey = request.headers.get("idempotency-key");
    if (idempotencyKey && db.idempotency.has(`project:${idempotencyKey}`)) {
      const existingId = db.idempotency.get(`project:${idempotencyKey}`)!;
      const existing = db.projects.get(existingId);
      if (existing) return ok(existing.project, { status: 201 });
    }
    const body = (await request.json()) as Record<string, unknown>;
    const name = String(body.name ?? "").trim();
    if (!name) {
      return fail(422, "VALIDATION_FAILED", "部分字段未通过校验。", {
        details: { field_errors: { name: "项目名称不能为空" } },
      });
    }
    const projectId = nextId(db, "proj");
    const hasTextbook = Boolean(body.textbook_file_object_id || body.textbook_library_id);
    const outputScope = (body.output_scope as { ppt?: boolean; video?: boolean } | undefined) ?? {};
    const project: Project = {
      project_id: projectId,
      name,
      subject: "primary_math",
      grade: Number(body.grade ?? 3),
      textbook_version: String(body.textbook_version ?? "人教版"),
      volume: String(body.volume ?? ""),
      status: "active",
      execution_mode: (body.execution_mode as Project["execution_mode"]) ?? "semi_auto",
      progress_percent: 0,
      textbook_status: hasTextbook ? "parsing" : "none",
      division_status: "none",
      lesson_count: 0,
      budget_minor_units: Number(body.budget_minor_units ?? db.budgets.project_default_minor_units ?? 30_000),
      spent_minor_units: 0,
      currency: "CNY",
      output_scope: { ppt: outputScope.ppt ?? true, video: outputScope.video ?? true },
      row_version: 1,
      created_at: minutesAgo(0),
      updated_at: minutesAgo(0),
    };
    db.projects.set(projectId, {
      project,
      evidence: null,
      division: null,
      divisionVersions: [],
      lessons: [],
      delivery: { status: "not_ready", items: [], blockers: [], package_task_id: null, packaged_at: null, package_file: null },
    });
    if (idempotencyKey) db.idempotency.set(`project:${idempotencyKey}`, projectId);
    if (hasTextbook) {
      startTask({
        taskType: "textbook_parse",
        projectId,
        durationMs: 12_000,
        failure: db.flags.parseFails
          ? { code: "PARSE_FAILED", message: "教材解析失败：部分页面版面无法识别。未产生模型费用，可直接重试。", retryable: true }
          : null,
        onComplete: (mockDb) => {
          const state = mockDb.projects.get(projectId);
          if (!state) return;
          state.evidence = makeArtifact({
            artifactType: "textbook_evidence",
            versionNumber: 1,
            status: "needs_review",
            content: buildEvidenceContent({ partial: mockDb.flags.evidencePartial }) as unknown as Record<string, unknown>,
            createdMinutesAgo: 0,
          });
          state.project.textbook_status = "evidence_ready";
          publishEvent({ event_type: "artifact.version_created", project_id: projectId, lesson_id: null, node_key: null, task_id: null, payload: { artifact_type: "textbook_evidence", artifact_version_id: state.evidence.artifact_version_id } });
        },
      });
    }
    return ok(project, { status: 201 });
  }),

  // ---------- 项目详情 / 更新 / 删除 / 归档 ----------
  http.get(api("/projects/:projectId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    return ok(state.project);
  }),

  http.patch(api("/projects/:projectId"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    const body = (await request.json()) as Record<string, unknown>;
    if (Number(body.row_version) !== state.project.row_version) {
      return fail(409, "VERSION_CONFLICT", "项目设置已在其他位置被修改。", {
        action: "reload",
        details: { server_row_version: state.project.row_version },
      });
    }
    if (typeof body.name === "string" && body.name.trim()) state.project.name = body.name.trim();
    if (typeof body.execution_mode === "string") state.project.execution_mode = body.execution_mode as Project["execution_mode"];
    if (typeof body.budget_minor_units === "number") state.project.budget_minor_units = body.budget_minor_units;
    if (body.output_scope && typeof body.output_scope === "object") {
      const scope = body.output_scope as { ppt?: boolean; video?: boolean };
      state.project.output_scope = {
        ppt: scope.ppt ?? state.project.output_scope?.ppt ?? true,
        video: scope.video ?? state.project.output_scope?.video ?? true,
      };
    }
    state.project.row_version += 1;
    state.project.updated_at = minutesAgo(0);
    return ok(state.project);
  }),

  http.delete(api("/projects/:projectId"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const db = getDb();
    const state = db.projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    if (state.project.status !== "draft") {
      return fail(409, "NOT_DELETABLE", "只有草稿项目可以删除；进行中的项目请使用归档。", { action: "archive_instead" });
    }
    db.projects.delete(state.project.project_id);
    return new Response(null, { status: 204 });
  }),

  http.post(api("/projects/:projectId/archive"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    state.project.status = "archived";
    state.project.row_version += 1;
    state.project.updated_at = minutesAgo(0);
    return ok(state.project);
  }),

  http.post(api("/projects/:projectId/restore"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    state.project.status = "active";
    state.project.row_version += 1;
    state.project.updated_at = minutesAgo(0);
    return ok(state.project);
  }),

  // ---------- 上传会话 ----------
  http.post(api("/projects/:projectId/upload-sessions"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const state = db.projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    const body = (await request.json()) as { file_name?: string; size_bytes?: number; mime_type?: string; source_type?: string };
    if ((body.size_bytes ?? 0) > 200 * 1024 * 1024) {
      return fail(413, "FILE_TOO_LARGE", "文件超过 200MB 上限，请压缩后重试。");
    }
    const sessionId = nextId(db, "upload");
    db.fileNames.set(`upload:${sessionId}`, JSON.stringify({ projectId: state.project.project_id, fileName: body.file_name ?? "文件", mimeType: body.mime_type ?? "application/octet-stream", sourceType: body.source_type ?? "textbook" }));
    return ok(
      {
        upload_session_id: sessionId,
        upload_url: `/api/v2/__mock-upload/${sessionId}`,
        method: "PUT" as const,
        required_headers: {},
        expires_at: minutesAgo(-30),
      },
      { status: 201 },
    );
  }),

  // Mock 直传端点
  http.put(api("/__mock-upload/:sessionId"), async () => {
    await simulateLatency();
    return new Response(null, { status: 200 });
  }),

  http.post(api("/upload-sessions/:uploadSessionId/complete"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const raw = db.fileNames.get(`upload:${String(params.uploadSessionId)}`);
    if (!raw) return fail(404, "NOT_FOUND", "上传会话不存在或已过期。");
    const info = JSON.parse(raw) as { projectId: string; fileName: string; mimeType: string; sourceType: string };
    const body = (await request.json()) as { sha256?: string; size_bytes?: number };
    const file = makeFileObject({ fileName: info.fileName, mimeType: info.mimeType, sizeBytes: body.size_bytes ?? 1_000_000 });
    const state = db.projects.get(info.projectId);
    let parseTask = null;
    if (state && info.sourceType === "textbook") {
      state.project.textbook_status = "parsing";
      parseTask = startTask({
        taskType: "textbook_parse",
        projectId: info.projectId,
        durationMs: 12_000,
        failure: db.flags.parseFails
          ? { code: "PARSE_FAILED", message: "教材解析失败：部分页面版面无法识别。未产生模型费用，可直接重试。", retryable: true }
          : null,
        onComplete: (mockDb) => {
          const projectState = mockDb.projects.get(info.projectId);
          if (!projectState) return;
          projectState.evidence = makeArtifact({
            artifactType: "textbook_evidence",
            versionNumber: (projectState.evidence?.version_number ?? 0) + 1,
            status: "needs_review",
            content: buildEvidenceContent({ partial: mockDb.flags.evidencePartial }) as unknown as Record<string, unknown>,
            createdMinutesAgo: 0,
          });
          projectState.project.textbook_status = "evidence_ready";
          publishEvent({ event_type: "artifact.version_created", project_id: info.projectId, lesson_id: null, node_key: null, task_id: null, payload: { artifact_type: "textbook_evidence", artifact_version_id: projectState.evidence.artifact_version_id } });
        },
      });
    }
    return ok({ file_object: file, parse_task: parseTask });
  }),

  // ---------- 教材证据 ----------
  http.get(api("/projects/:projectId/textbook-evidence/current"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    if (!state.evidence) return fail(404, "EVIDENCE_NOT_READY", "教材还没有完成解析。", { action: "upload_textbook" });
    return ok(state.evidence);
  }),

  http.post(api("/projects/:projectId/textbook-evidence/corrections"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const state = db.projects.get(String(params.projectId));
    if (!state?.evidence) return fail(404, "NOT_FOUND", "教材证据不存在。");
    const body = (await request.json()) as { corrections?: Array<{ page_number: number; field: string; corrected_value: string }>; row_version?: number };
    if (Number(body.row_version) !== state.evidence.row_version) {
      return fail(409, "VERSION_CONFLICT", "教材证据已被修改，请刷新后重试。", { details: { server_row_version: state.evidence.row_version } });
    }
    const content = state.evidence.content as ReturnType<typeof buildEvidenceContent>;
    for (const correction of body.corrections ?? []) {
      const page = content.pages.find((p) => p.page_number === correction.page_number);
      if (page) {
        page.ocr_text = correction.corrected_value;
        page.low_confidence = false;
      }
    }
    state.evidence = makeArtifact({
      artifactType: "textbook_evidence",
      versionNumber: state.evidence.version_number + 1,
      status: "needs_review",
      content: content as unknown as Record<string, unknown>,
      source: "corrected",
      createdMinutesAgo: 0,
    });
    return ok(state.evidence);
  }),

  // ---------- 课时划分 ----------
  http.get(api("/projects/:projectId/lesson-divisions/current"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    if (!state.division) return fail(404, "DIVISION_NOT_READY", "课时划分还未生成。", { action: "generate_division" });
    return ok(state.division);
  }),

  http.get(api("/projects/:projectId/lesson-divisions/versions"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const state = getDb().projects.get(String(params.projectId));
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    return ok(state.divisionVersions);
  }),

  http.patch(api("/projects/:projectId/lesson-divisions/current"), async ({ params, request }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const state = db.projects.get(String(params.projectId));
    if (!state?.division) return fail(404, "NOT_FOUND", "课时划分不存在。");
    const body = (await request.json()) as { content?: DivisionContent; row_version?: number };
    if (db.flags.divisionConflictOnSave && !db.divisionConflictServed) {
      db.divisionConflictServed = true;
      state.division.row_version = (state.division.row_version ?? 1) + 1;
      return fail(409, "VERSION_CONFLICT", "课时划分已在其他窗口被修改。", {
        action: "resolve_conflict",
        details: { server_row_version: state.division.row_version, server_version_id: state.division.artifact_version_id },
      });
    }
    if (Number(body.row_version) !== state.division.row_version) {
      return fail(409, "VERSION_CONFLICT", "课时划分已在其他窗口被修改。", {
        action: "resolve_conflict",
        details: { server_row_version: state.division.row_version, server_version_id: state.division.artifact_version_id },
      });
    }
    const next = makeArtifact({
      artifactType: "lesson_division",
      versionNumber: state.division.version_number + 1,
      status: "needs_review",
      content: (body.content ?? state.division.content) as Record<string, unknown>,
      source: "edited",
      createdMinutesAgo: 0,
    });
    state.division.status = "superseded";
    state.division = next;
    state.divisionVersions.unshift(next);
    state.project.division_status = "needs_review";
    return ok(next);
  }),

  http.post(api("/projects/:projectId/lesson-divisions/runs"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    const db = getDb();
    const projectId = String(params.projectId);
    const state = db.projects.get(projectId);
    if (!state) return fail(404, "NOT_FOUND", "项目不存在或不可访问。");
    if (!state.evidence || state.evidence.status !== "approved") {
      return fail(409, "EVIDENCE_NOT_APPROVED", "请先确认教材解析结果，再生成课时划分。", { action: "review_evidence" });
    }
    state.project.division_status = "generating";
    const task = startTask({
      taskType: "lesson_division_generate",
      projectId,
      durationMs: 8000,
      estimatedCostMinor: 60,
      actualCostMinor: 55,
      providerName: "启明文本云",
      onComplete: (mockDb) => {
        const projectState = mockDb.projects.get(projectId);
        if (!projectState) return;
        const artifact = makeArtifact({
          artifactType: "lesson_division",
          versionNumber: (projectState.division?.version_number ?? 0) + 1,
          status: "needs_review",
          content: buildDivisionContent() as unknown as Record<string, unknown>,
          createdMinutesAgo: 0,
        });
        if (projectState.division) projectState.division.status = "superseded";
        projectState.division = artifact;
        projectState.divisionVersions.unshift(artifact);
        projectState.project.division_status = "needs_review";
        publishEvent({ event_type: "artifact.version_created", project_id: projectId, lesson_id: null, node_key: null, task_id: null, payload: { artifact_type: "lesson_division", artifact_version_id: artifact.artifact_version_id } });
      },
    });
    return ok(task, { status: 202 });
  }),

  http.post(api("/projects/:projectId/lesson-divisions/:versionId/approve"), async ({ params }) => {
    const unauth = guard();
    if (unauth) return unauth;
    await simulateLatency();
    const db = getDb();
    const state = db.projects.get(String(params.projectId));
    if (!state?.division) return fail(404, "NOT_FOUND", "课时划分不存在。");
    if (state.division.artifact_version_id !== String(params.versionId)) {
      return fail(409, "NOT_CURRENT_VERSION", "只能批准当前最新版本的课时划分。", { action: "reload" });
    }
    state.division.status = "approved";
    state.division.approved_at = minutesAgo(0);
    state.project.division_status = "approved";
    const content = state.division.content as unknown as DivisionContent;
    if (state.lessons.length === 0) {
      state.lessons = content.lessons.map((lesson, index) =>
        makeFreshLessonState(state.project.project_id, nextId(db, "lesson"), index + 1, lesson.title, lesson.lesson_type),
      );
      state.project.lesson_count = state.lessons.length;
    }
    publishEvent({ event_type: "artifact.approved", project_id: state.project.project_id, lesson_id: null, node_key: null, task_id: null, payload: { artifact_version_id: state.division.artifact_version_id, artifact_type: "lesson_division" } });
    return ok(state.lessons.map((l) => l.lesson));
  }),
];
