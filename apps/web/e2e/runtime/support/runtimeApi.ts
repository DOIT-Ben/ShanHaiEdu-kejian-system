import { expect, type Page, type Route } from "@playwright/test";
import type { components } from "@/generated/api-schema";

export const projectId = "01960000-0000-7000-8000-000000000001";
export const uploadSessionId = "01960000-0000-7000-8000-000000000002";
export const jobId = "01960000-0000-7000-8000-000000000003";
export const materialId = "01960000-0000-7000-8000-000000000004";
export const lessonId = "01960000-0000-7000-8000-000000000101";
export const artifactId = "01960000-0000-7000-8000-000000000301";
export const assetSlotId = "01960000-0000-7000-8000-000000000401";
export const assetBindingId = "01960000-0000-7000-8000-000000000402";
export const fileAssetVersionId = "01960000-0000-7000-8000-000000000403";
const workflowVersionId = "01960000-0000-7000-8000-000000000201";
const now = "2026-07-20T08:00:00Z";

export type RuntimeApiState = {
  artifactApprovals: number;
  artifactReads: number;
  artifactSubmits: number;
  assetBinds: number;
  assetPackageReads: number;
  assetSlotReads: number;
  assetUnbinds: number;
  confirmRequests: number;
  createProjectRequests: number;
  csrfHeaders: string[];
  idempotencyHeaders: string[];
  ifMatchHeaders: string[];
  jobCancelRequests: number;
  jobCancelIdempotencyHeaders: string[];
  jobReads: number;
  jobStreamRequests: number;
  lessonBranchWrites: number;
  lessonCollectionWrites: number;
  materialFileReads: number;
  materialParseReads: number;
  projectStreamRequests: number;
  unhandled: string[];
  uploadFileRequests: number;
  uploadSessionRequests: number;
  writeRequests: number;
};

type RuntimeApiOptions = {
  completeJobAfterStream?: boolean;
  emptyLessons?: boolean;
  failFirstJobCancelAfterAccept?: boolean;
  failFirstUploadSession?: boolean;
  jobStatus?: "cancelled" | "failed" | "running" | "succeeded";
};

const baseProject = {
  id: projectId,
  title: "认识百分数",
  subject: "primary_math" as const,
  grade: "六年级",
  textbook_edition: "人教版",
  knowledge_point: "百分数的意义",
  status: "active" as const,
  execution_mode: "guided" as const,
  content_release_id: "01960000-0000-7000-8000-000000000202",
  workflow_definition_version_id: workflowVersionId,
  created_at: now,
  updated_at: now,
};

const lesson = {
  id: lessonId,
  project_id: projectId,
  lesson_key: "lesson-1",
  position: 1,
  title: "百分数的意义",
  scope_summary: "借助百格图理解百分数表示一个数是另一个数的百分之几。",
  objective_summary: "能读写常见百分数并说明它与整体的关系。",
  estimated_minutes: 40,
  source_division_version_id: "01960000-0000-7000-8000-000000000102",
  status: "active" as const,
  lock_version: 1,
  branches: [
    { branch_key: "lesson_plan", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "intro_options", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "ppt", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "video", enabled: true, workflow_status: "not_ready", settings: {} },
  ],
  created_at: now,
  updated_at: now,
};

const fileAsset = {
  id: "01960000-0000-7000-8000-000000000404",
  asset_key: "六年级百分数教材.pdf",
  asset_kind: "source_material",
  status: "active" as const,
  retention_class: "project_source",
  lock_version: 1,
  current_version: {
    id: fileAssetVersionId,
    version_no: 1,
    mime_type: "application/pdf",
    byte_size: 256_000,
    sha256: "a".repeat(64),
    width: null,
    height: null,
    duration_ms: null,
    page_count: 8,
    scan_status: "clean" as const,
    derived_from_version_id: null,
    created_at: now,
  },
};

const parseVersion = {
  id: "01960000-0000-7000-8000-000000000405",
  source_material_id: materialId,
  file_asset_version_id: fileAssetVersionId,
  generation_job_id: jobId,
  version_no: 1,
  status: "succeeded" as const,
  parser_name: "server-parser",
  parser_version: "1.0",
  page_count: 8,
  text_checksum: "b".repeat(64),
  validation_report: {},
  error_code: null,
  created_at: now,
  started_at: now,
  completed_at: now,
};

const artifactVersion = {
  id: "01960000-0000-7000-8000-000000000302",
  version_no: 1,
  content: { title: "百分数的意义" },
  content_hash: "c".repeat(64),
  render_summary: {},
  source_kind: "manual" as const,
  source_node_run_id: null,
  context_snapshot_id: null,
  prompt_snapshot_id: null,
  validation_report: {},
  created_at: now,
  created_by: "01960000-0000-7000-8000-000000000999",
};

const baseArtifact = {
  id: artifactId,
  project_id: projectId,
  lesson_unit_id: lessonId,
  branch_key: "lesson_plan",
  artifact_key: "lesson-plan",
  artifact_type: "lesson_plan",
  content_definition_version_id: "01960000-0000-7000-8000-000000000303",
  status: "in_review" as const,
  stale_reason: null,
  lock_version: 1,
  current_draft: {
    id: "01960000-0000-7000-8000-000000000304",
    draft_branch: "main",
    content: { title: "百分数的意义" },
    validation_report: {},
    based_on_version_id: null,
    autosaved_at: now,
    lock_version: 1,
  },
  current_submitted_version: artifactVersion,
  current_approved_version: null,
  created_at: now,
  updated_at: now,
};

const baseBinding = {
  id: assetBindingId,
  project_asset_slot_id: assetSlotId,
  file_asset_version_id: fileAssetVersionId,
  source_artifact_version_id: null,
  position: 1,
  is_active: true,
  bound_at: now,
  bound_by: "01960000-0000-7000-8000-000000000999",
  unbound_at: null,
  unbound_by: null,
};

const assetSlot = {
  id: assetSlotId,
  project_id: projectId,
  lesson_unit_id: lessonId,
  slot_key: "lesson.cover",
  asset_type: "image",
  cardinality: "one" as const,
  required: true,
  status: "satisfied" as const,
  target_contract: { allowed_mime_types: ["image/png"], require_clean_scan: true },
  active_bindings: [baseBinding],
};

function envelope<T>(data: T, requestId: string) {
  return { data, request_id: requestId };
}

function errorEnvelope(code: string, message: string, retryable = false) {
  return {
    error: { code, message, retryable },
    request_id: `req_${code.toLowerCase()}`,
  };
}

function sseBody(
  sequence: number,
  eventType: string,
  resource: { id: string; type: string },
  payload: Record<string, unknown>,
) {
  const eventIdSuffix = String(9_000 + sequence).padStart(12, "0");
  const event = {
    event_id: `01960000-0000-7000-8000-${eventIdSuffix}`,
    sequence_no: sequence,
    event_type: eventType,
    occurred_at: now,
    project_id: projectId,
    resource,
    payload,
    request_id: `req_evt_${String(sequence)}`,
  };
  return `id: ${String(sequence)}\r\nevent: ${eventType}\r\ndata: ${JSON.stringify(event)}\r\n\r\n`;
}

async function json(route: Route, body: unknown, status = 200, headers?: Record<string, string>) {
  await route.fulfill({
    body: JSON.stringify(body),
    contentType: "application/json",
    headers,
    status,
  });
}

export async function installRuntimeApi(page: Page, options: RuntimeApiOptions = {}) {
  let currentProject = {
    ...baseProject,
    execution_mode: baseProject.execution_mode as "guided" | "automatic",
  };
  let currentLesson = structuredClone(lesson) as components["schemas"]["Lesson"];
  let currentArtifact = structuredClone(
    baseArtifact,
  ) as unknown as components["schemas"]["Artifact"];
  let currentBinding = structuredClone(baseBinding) as components["schemas"]["AssetBinding"];
  const state: RuntimeApiState = {
    artifactApprovals: 0,
    artifactReads: 0,
    artifactSubmits: 0,
    assetBinds: 0,
    assetPackageReads: 0,
    assetSlotReads: 0,
    assetUnbinds: 0,
    confirmRequests: 0,
    createProjectRequests: 0,
    csrfHeaders: [],
    idempotencyHeaders: [],
    ifMatchHeaders: [],
    jobCancelRequests: 0,
    jobCancelIdempotencyHeaders: [],
    jobReads: 0,
    jobStreamRequests: 0,
    lessonBranchWrites: 0,
    lessonCollectionWrites: 0,
    materialFileReads: 0,
    materialParseReads: 0,
    projectStreamRequests: 0,
    unhandled: [],
    uploadFileRequests: 0,
    uploadSessionRequests: 0,
    writeRequests: 0,
  };

  await page.route("https://storage.runtime.test/**", async (route) => {
    const request = route.request();
    const corsHeaders = {
      "Access-Control-Allow-Headers": "Content-Type, X-Upload-Token",
      "Access-Control-Allow-Methods": "PUT, OPTIONS",
      "Access-Control-Allow-Origin": "http://127.0.0.1:4176",
      "Access-Control-Expose-Headers": "ETag",
    };
    if (request.method() === "OPTIONS") {
      await route.fulfill({ headers: corsHeaders, status: 204 });
      return;
    }
    expect(request.method()).toBe("PUT");
    expect(request.headers()["x-upload-token"]).toBe("runtime-upload-token");
    state.uploadFileRequests += 1;
    await route.fulfill({
      body: "",
      headers: { ...corsHeaders, ETag: '"runtime-material-v1"' },
      status: 200,
    });
  });

  await page.route("**/api/v2/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      state.writeRequests += 1;
      state.csrfHeaders.push(request.headers()["x-csrf-token"] ?? "");
      state.idempotencyHeaders.push(request.headers()["idempotency-key"] ?? "");
      state.ifMatchHeaders.push(request.headers()["if-match"] ?? "");
    }

    if (method === "GET" && path === "/api/v2/projects") {
      await json(route, {
        data: { items: [baseProject] },
        meta: { next_cursor: null },
        request_id: "req_projects",
      });
      return;
    }

    if (method === "POST" && path === "/api/v2/projects") {
      state.createProjectRequests += 1;
      const body = request.postDataJSON() as {
        execution_mode?: string;
        grade?: string;
        knowledge_point?: string;
        textbook_edition?: string;
        title?: string;
      };
      currentProject = {
        ...baseProject,
        execution_mode: body.execution_mode === "automatic" ? "automatic" : "guided",
        grade: body.grade ?? baseProject.grade,
        knowledge_point: body.knowledge_point ?? baseProject.knowledge_point,
        textbook_edition: body.textbook_edition ?? baseProject.textbook_edition,
        title: body.title ?? baseProject.title,
      };
      await json(route, envelope(currentProject, "req_create_project"), 201);
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}`) {
      await json(route, envelope(currentProject, "req_project"), 200, { ETag: '"project-v1"' });
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/lessons`) {
      const items = options.emptyLessons ? [] : [currentLesson];
      await json(
        route,
        envelope({ items, lock_version: options.emptyLessons ? 0 : 1 }, "req_lessons"),
        200,
        { ETag: options.emptyLessons ? '"lessons-v0"' : '"lessons-v1"' },
      );
      return;
    }

    if (method === "PATCH" && path === `/api/v2/projects/${projectId}/lessons`) {
      state.lessonCollectionWrites += 1;
      const body = request.postDataJSON() as {
        items: Array<
          Pick<
            typeof currentLesson,
            | "estimated_minutes"
            | "id"
            | "objective_summary"
            | "position"
            | "scope_summary"
            | "title"
          >
        >;
      };
      const update = body.items.find((item) => item.id === lessonId);
      if (update) currentLesson = { ...currentLesson, ...update, lock_version: 2, updated_at: now };
      await json(
        route,
        envelope({ items: [currentLesson], lock_version: 2 }, "req_update_lessons"),
        200,
        { ETag: '"lessons-v2"' },
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/lessons/${lessonId}`) {
      await json(route, envelope(currentLesson, "req_lesson"), 200, { ETag: '"lesson-v1"' });
      return;
    }

    if (method === "PATCH" && path === `/api/v2/lessons/${lessonId}/branches`) {
      state.lessonBranchWrites += 1;
      const body = request.postDataJSON() as { branches: typeof currentLesson.branches };
      currentLesson = {
        ...currentLesson,
        branches: body.branches,
        lock_version: 2,
        updated_at: now,
      };
      await json(route, envelope(currentLesson, "req_update_lesson_branches"), 200, {
        ETag: '"lesson-v2"',
      });
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/automation-policy`) {
      await json(
        route,
        envelope(
          {
            project_id: projectId,
            workflow_definition_version_id: workflowVersionId,
            mode: "guided",
            node_rules: [],
            policy_version: 1,
            updated_at: now,
          },
          "req_policy",
        ),
        200,
        { ETag: '"policy-v1"' },
      );
      return;
    }

    if (method === "PATCH" && path === `/api/v2/projects/${projectId}/automation-policy`) {
      const body = request.postDataJSON() as { mode: "automatic" | "guided" };
      await json(
        route,
        envelope(
          {
            project_id: projectId,
            workflow_definition_version_id: workflowVersionId,
            mode: body.mode,
            node_rules: [],
            policy_version: 2,
            updated_at: now,
          },
          "req_update_policy",
        ),
        200,
        { ETag: '"policy-v2"' },
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/events/stream`) {
      state.projectStreamRequests += 1;
      await route.fulfill({
        body: sseBody(
          1,
          "project.created",
          { id: projectId, type: "project" },
          { status: "active" },
        ),
        headers: { "Cache-Control": "no-cache", "Content-Type": "text/event-stream" },
        status: 200,
      });
      return;
    }

    if (method === "POST" && path === `/api/v2/projects/${projectId}/materials/uploads`) {
      state.uploadSessionRequests += 1;
      if (options.failFirstUploadSession && state.uploadSessionRequests === 1) {
        await json(
          route,
          errorEnvelope("UPLOAD_SESSION_UNAVAILABLE", "教材上传入口暂时不可用", true),
          503,
        );
        return;
      }
      await json(
        route,
        envelope(
          {
            upload_session_id: uploadSessionId,
            material_id: materialId,
            upload_url: "https://storage.runtime.test/material",
            method: "PUT",
            required_headers: { "X-Upload-Token": "runtime-upload-token" },
            expires_at: "2030-01-01T00:00:00Z",
          },
          "req_upload_session",
        ),
        201,
      );
      return;
    }

    if (
      method === "POST" &&
      path === `/api/v2/projects/${projectId}/materials/${materialId}/confirm`
    ) {
      state.confirmRequests += 1;
      await json(
        route,
        envelope(
          {
            job_id: jobId,
            status: "queued",
            events_url: `/api/v2/generation-jobs/${jobId}/events/stream`,
          },
          "req_confirm",
        ),
        202,
      );
      return;
    }

    if (
      method === "GET" &&
      path === `/api/v2/projects/${projectId}/materials/${materialId}/file-asset`
    ) {
      state.materialFileReads += 1;
      await json(route, envelope(fileAsset, "req_material_file"), 200, {
        ETag: '"material-file-v1"',
      });
      return;
    }

    if (
      method === "GET" &&
      path === `/api/v2/projects/${projectId}/materials/${materialId}/parse-versions`
    ) {
      state.materialParseReads += 1;
      await json(route, envelope({ items: [parseVersion] }, "req_material_parses"));
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/asset-slots`) {
      state.assetSlotReads += 1;
      const slot = {
        ...assetSlot,
        active_bindings: currentBinding.is_active ? [currentBinding] : [],
      };
      await json(route, {
        data: { items: [slot] },
        meta: { next_cursor: null },
        request_id: "req_asset_slots",
      });
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/asset-package`) {
      state.assetPackageReads += 1;
      const slot = {
        ...assetSlot,
        active_bindings: currentBinding.is_active ? [currentBinding] : [],
      };
      await json(route, {
        data: { items: [slot], project_id: projectId },
        meta: { next_cursor: null },
        request_id: "req_asset_package",
      });
      return;
    }

    if (method === "POST" && path === `/api/v2/asset-slots/${assetSlotId}/bindings`) {
      state.assetBinds += 1;
      const body = request.postDataJSON() as {
        file_asset_version_id: string;
        source_artifact_version_id: string | null;
      };
      currentBinding = {
        ...baseBinding,
        file_asset_version_id: body.file_asset_version_id,
        source_artifact_version_id: body.source_artifact_version_id,
      };
      await json(route, envelope(currentBinding, "req_bind_asset"), 201);
      return;
    }

    if (method === "POST" && path === `/api/v2/asset-bindings/${assetBindingId}/unbind`) {
      state.assetUnbinds += 1;
      const unbound = {
        ...currentBinding,
        is_active: false,
        unbound_at: now,
        unbound_by: "01960000-0000-7000-8000-000000000999",
      };
      currentBinding = { ...currentBinding, is_active: false };
      await json(route, envelope(unbound, "req_unbind_asset"));
      return;
    }

    if (method === "GET" && path === `/api/v2/artifacts/${artifactId}`) {
      state.artifactReads += 1;
      await json(route, envelope(currentArtifact, "req_artifact"), 200, {
        ETag: '"artifact-v1"',
      });
      return;
    }

    if (method === "PUT" && path === `/api/v2/artifacts/${artifactId}/drafts/main`) {
      const body = request.postDataJSON() as components["schemas"]["SaveArtifactDraftRequest"];
      const currentDraft = currentArtifact.current_draft;
      if (!currentDraft) {
        await json(route, errorEnvelope("ARTIFACT_DRAFT_NOT_FOUND", "草稿不存在"), 404);
        return;
      }
      const draft = { ...currentDraft, content: body.content, autosaved_at: now };
      currentArtifact = { ...currentArtifact, current_draft: draft, updated_at: now };
      await json(route, envelope(draft, "req_save_artifact_draft"), 200, {
        ETag: '"artifact-v2"',
      });
      return;
    }

    if (method === "POST" && path === `/api/v2/artifacts/${artifactId}/versions`) {
      state.artifactSubmits += 1;
      await json(route, envelope(artifactVersion, "req_submit_artifact"), 201);
      return;
    }

    if (method === "POST" && path === `/api/v2/artifact-versions/${artifactVersion.id}/approvals`) {
      state.artifactApprovals += 1;
      await json(
        route,
        envelope(
          {
            id: "01960000-0000-7000-8000-000000000305",
            artifact_version_id: artifactVersion.id,
            action: "approve",
            actor_type: "user",
            actor_user_id: "01960000-0000-7000-8000-000000000999",
            comment: null,
            quality_evidence: {},
            policy_snapshot: {},
            created_at: now,
          },
          "req_approve_artifact",
        ),
        201,
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/generation-jobs/${jobId}`) {
      state.jobReads += 1;
      const status =
        options.completeJobAfterStream && state.jobStreamRequests > 0
          ? "succeeded"
          : (options.jobStatus ?? "succeeded");
      await json(
        route,
        envelope(
          {
            id: jobId,
            project_id: projectId,
            job_type: "parse_material",
            status,
            progress_percent: status === "succeeded" ? 100 : 48,
            progress_message:
              status === "succeeded"
                ? "教材已经整理完成"
                : status === "failed"
                  ? "教材处理没有完成"
                  : "正在整理教材内容",
            error_code: status === "failed" ? "MATERIAL_PARSE_FAILED" : null,
            created_at: now,
            updated_at: now,
          },
          "req_job",
        ),
      );
      return;
    }

    if (method === "POST" && path === `/api/v2/generation-jobs/${jobId}/cancel`) {
      state.jobCancelRequests += 1;
      state.jobCancelIdempotencyHeaders.push(request.headers()["idempotency-key"] ?? "");
      if (options.failFirstJobCancelAfterAccept && state.jobCancelRequests === 1) {
        await route.abort("failed");
        return;
      }
      await json(
        route,
        envelope(
          {
            id: jobId,
            project_id: projectId,
            job_type: "parse_material",
            status: "cancel_requested",
            progress_percent: 48,
            progress_message: "正在取消任务",
            error_code: null,
            created_at: now,
            updated_at: now,
          },
          "req_cancel_job",
        ),
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/generation-jobs/${jobId}/events/stream`) {
      state.jobStreamRequests += 1;
      await route.fulfill({
        body: sseBody(
          1,
          "generation.job.progress",
          { id: jobId, type: "generation_job" },
          { progress_percent: 100, status: "succeeded" },
        ),
        headers: { "Cache-Control": "no-cache", "Content-Type": "text/event-stream" },
        status: 200,
      });
      return;
    }

    state.unhandled.push(`${method} ${path}`);
    await json(route, errorEnvelope("UNHANDLED_RUNTIME_TEST_ROUTE", `${method} ${path}`), 501);
  });

  return state;
}
