import { expect, type Page, type Route } from "@playwright/test";

export const projectId = "01960000-0000-7000-8000-000000000001";
export const uploadSessionId = "01960000-0000-7000-8000-000000000002";
export const jobId = "01960000-0000-7000-8000-000000000003";
export const materialId = "01960000-0000-7000-8000-000000000004";
export const lessonId = "01960000-0000-7000-8000-000000000101";
const workflowVersionId = "01960000-0000-7000-8000-000000000201";
const now = "2026-07-20T08:00:00Z";

export type RuntimeApiState = {
  confirmRequests: number;
  createProjectRequests: number;
  csrfHeaders: string[];
  idempotencyHeaders: string[];
  jobReads: number;
  jobStreamRequests: number;
  projectStreamRequests: number;
  unhandled: string[];
  uploadFileRequests: number;
  uploadSessionRequests: number;
  writeRequests: number;
};

type RuntimeApiOptions = {
  failFirstUploadSession?: boolean;
  jobStatus?: "running" | "succeeded";
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
  const event = {
    event_id: `evt-${String(sequence)}-${resource.id}`,
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
  const state: RuntimeApiState = {
    confirmRequests: 0,
    createProjectRequests: 0,
    csrfHeaders: [],
    idempotencyHeaders: [],
    jobReads: 0,
    jobStreamRequests: 0,
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
      await json(
        route,
        envelope(
          {
            ...baseProject,
            execution_mode: body.execution_mode ?? "guided",
            grade: body.grade ?? baseProject.grade,
            knowledge_point: body.knowledge_point ?? baseProject.knowledge_point,
            textbook_edition: body.textbook_edition ?? baseProject.textbook_edition,
            title: body.title ?? baseProject.title,
          },
          "req_create_project",
        ),
        201,
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}`) {
      await json(route, envelope(baseProject, "req_project"), 200, { ETag: '"project-v1"' });
      return;
    }

    if (method === "GET" && path === `/api/v2/projects/${projectId}/lessons`) {
      await json(route, envelope({ items: [lesson], lock_version: 1 }, "req_lessons"), 200, {
        ETag: '"lessons-v1"',
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

    if (method === "GET" && path === `/api/v2/projects/${projectId}/events/stream`) {
      state.projectStreamRequests += 1;
      await route.fulfill({
        body: sseBody(
          1,
          "project.updated",
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

    if (method === "GET" && path === `/api/v2/generation-jobs/${jobId}`) {
      state.jobReads += 1;
      const status = options.jobStatus ?? "succeeded";
      await json(
        route,
        envelope(
          {
            id: jobId,
            project_id: projectId,
            job_type: "parse_material",
            status,
            progress_percent: status === "succeeded" ? 100 : 48,
            progress_message: status === "succeeded" ? "教材已经整理完成" : "正在整理教材内容",
            error_code: null,
            created_at: now,
            updated_at: now,
          },
          "req_job",
        ),
      );
      return;
    }

    if (method === "GET" && path === `/api/v2/generation-jobs/${jobId}/events/stream`) {
      state.jobStreamRequests += 1;
      await route.fulfill({
        body: sseBody(
          1,
          "generation_job.succeeded",
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
