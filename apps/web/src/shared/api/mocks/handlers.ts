import { http, HttpResponse } from "msw";
import type { components } from "@/generated/api-schema";
import { apiConfig } from "@/shared/api/config";
import {
  contractArtifact,
  contractArtifactDraft,
  contractArtifactVersion,
  contractAssetBinding,
  contractAssetSlot,
  contractAutomationPolicy,
  contractFileAsset,
  contractIds,
  contractJob,
  contractNow,
  contractParseVersion,
  contractProject,
  contractPromptVersion,
  contractWorkflow,
  lessonFixture,
  projectFixture,
} from "@/shared/api/mocks/fixtures";

type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

function errorResponse(code: string, message: string, requestId: string, status: number) {
  const body = {
    error: { code, message, retryable: status >= 500 },
    request_id: requestId,
  } satisfies Schema<"error-envelope.schema">;
  return HttpResponse.json(body, { status });
}

function requireCsrf(request: Request) {
  if (request.headers.get("X-CSRF-Token")?.trim()) return undefined;
  return errorResponse(
    "CSRF_TOKEN_REQUIRED",
    "安全校验尚未就绪，请刷新页面后重试",
    "contract_csrf_required",
    403,
  );
}

function scenario(request: Request) {
  return (
    request.headers.get("X-Contract-Scenario") ??
    new URL(request.url).searchParams.get("scenario") ??
    "success"
  );
}

function contractSse(
  request: Request,
  eventType: string,
  resource: { id: string; type: string },
  projectId: string | null,
  payload: Record<string, unknown>,
) {
  const lastSequence = Number.parseInt(request.headers.get("Last-Event-ID") ?? "0", 10);
  const sequence = Number.isSafeInteger(lastSequence) && lastSequence > 0 ? lastSequence + 1 : 1;
  const data = {
    event_id: "01970000-0000-7000-8000-000000000999",
    sequence_no: sequence,
    event_type: eventType,
    occurred_at: contractNow,
    project_id: projectId,
    resource,
    payload,
    request_id: null,
  };
  return new HttpResponse(
    `id: ${String(sequence)}\nevent: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`,
    { headers: { "Cache-Control": "no-cache", "Content-Type": "text/event-stream" } },
  );
}

export const handlers = [
  http.get(`${apiConfig.baseUrl}/health/live`, () => {
    const body = {
      data: { status: "ok", service: "shanhaiedu-api", environment: "development" },
      request_id: "contract_health_live",
    } satisfies Schema<"LivenessEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/health/ready`, () => {
    const body = {
      data: {
        status: "ready",
        dependencies: [
          { name: "postgresql", ready: true, status: "available" },
          { name: "redis", ready: true, status: "available" },
          { name: "object_storage", ready: true, status: "available" },
        ],
      },
      request_id: "contract_health_ready",
    } satisfies Schema<"ReadinessEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/projects`, ({ request }) => {
    if (scenario(request) === "error")
      return errorResponse(
        "PROJECT_LIST_UNAVAILABLE",
        "项目暂时无法读取",
        "contract_projects_error",
        503,
      );
    const body = {
      data: { items: scenario(request) === "empty" ? [] : [contractProject] },
      meta: { next_cursor: null },
      request_id: "contract_projects",
    } satisfies Schema<"ProjectListEnvelope">;
    return HttpResponse.json(body);
  }),

  http.post(`${apiConfig.baseUrl}/projects`, async ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const input = (await request.json()) as Schema<"CreateProjectRequest">;
    const project = {
      ...contractProject,
      title: input.title,
      grade: input.grade ?? null,
      textbook_edition: input.textbook_edition ?? null,
      knowledge_point: input.knowledge_point,
      execution_mode:
        input.execution_mode ?? (input.automation_mode === "automatic" ? "automatic" : "guided"),
    } satisfies Schema<"CurrentProject">;
    const body = {
      data: project,
      request_id: "contract_create_project",
    } satisfies Schema<"ProjectEnvelope">;
    return HttpResponse.json(body, { status: 201 });
  }),

  http.get(`${apiConfig.baseUrl}/projects/:projectId`, ({ params, request }) => {
    if (scenario(request) === "not-found")
      return errorResponse("PROJECT_NOT_FOUND", "项目不存在", "contract_project_not_found", 404);
    const body = {
      data: projectFixture(String(params.projectId)),
      request_id: "contract_project",
    } satisfies Schema<"ProjectEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"project-v3"' } });
  }),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/automation-policy`, ({ params }) => {
    const body = {
      data: { ...contractAutomationPolicy, project_id: String(params.projectId) },
      request_id: "contract_policy",
    } satisfies Schema<"AutomationPolicyEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"policy-v3"' } });
  }),

  http.patch(
    `${apiConfig.baseUrl}/projects/:projectId/automation-policy`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      if (scenario(request) === "conflict")
        return errorResponse(
          "EDIT_CONFLICT",
          "自动化设置已被更新",
          "contract_policy_conflict",
          409,
        );
      const input = (await request.json()) as Schema<"UpdateAutomationPolicyRequest">;
      const policy = {
        ...contractAutomationPolicy,
        project_id: String(params.projectId),
        mode: input.mode ?? contractAutomationPolicy.mode,
        node_rules: input.node_rules ?? contractAutomationPolicy.node_rules,
        policy_version: contractAutomationPolicy.policy_version + 1,
      } satisfies Schema<"AutomationPolicy">;
      const body = {
        data: policy,
        request_id: "contract_policy_update",
      } satisfies Schema<"AutomationPolicyEnvelope">;
      return HttpResponse.json(body, { headers: { ETag: '"policy-v4"' } });
    },
  ),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/lessons`, ({ params, request }) => {
    const items =
      scenario(request) === "empty"
        ? []
        : [lessonFixture(contractIds.lessonId, String(params.projectId))];
    const body = {
      data: { items, lock_version: 2 },
      request_id: "contract_lessons",
    } satisfies Schema<"LessonCollectionEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"lessons-v2"' } });
  }),

  http.patch(`${apiConfig.baseUrl}/projects/:projectId/lessons`, async ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    if (scenario(request) === "conflict" || request.headers.get("If-Match") === '"stale"')
      return errorResponse("EDIT_CONFLICT", "课时集合已被更新", "contract_lessons_conflict", 409);
    const input = (await request.json()) as Schema<"UpdateLessonCollectionRequest">;
    const items = input.items.map((item) => ({
      ...lessonFixture(item.id, String(params.projectId)),
      ...item,
      lock_version: 3,
      updated_at: contractNow,
    })) satisfies Schema<"Lesson">[];
    const body = {
      data: { items, lock_version: 3 },
      request_id: "contract_lessons_update",
    } satisfies Schema<"LessonCollectionEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"lessons-v3"' } });
  }),

  http.get(`${apiConfig.baseUrl}/lessons/:lessonId`, ({ params }) => {
    const body = {
      data: lessonFixture(String(params.lessonId)),
      request_id: "contract_lesson",
    } satisfies Schema<"LessonEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"lesson-v2"' } });
  }),

  http.patch(`${apiConfig.baseUrl}/lessons/:lessonId/branches`, async ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    if (scenario(request) === "conflict")
      return errorResponse("EDIT_CONFLICT", "课时分支已被更新", "contract_branches_conflict", 409);
    const input = (await request.json()) as Schema<"UpdateLessonBranchesRequest">;
    const lesson = {
      ...lessonFixture(String(params.lessonId)),
      branches: input.branches.map((branch) => ({
        ...branch,
        workflow_status: branch.enabled ? "not_ready" : "disabled",
      })),
      lock_version: 3,
    } satisfies Schema<"Lesson">;
    const body = {
      data: lesson,
      request_id: "contract_branches_update",
    } satisfies Schema<"LessonEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"lesson-v3"' } });
  }),

  http.post(`${apiConfig.baseUrl}/projects/:projectId/materials/uploads`, async ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const input = (await request.json()) as Schema<"CreateUploadSessionRequest">;
    if (input.media_type !== "application/pdf")
      return errorResponse(
        "UNSUPPORTED_MEDIA_TYPE",
        "教材只支持 PDF 文件",
        "contract_upload_type",
        422,
      );
    const uploadUrl = new URL(
      `/__contract-upload/${contractIds.uploadSessionId}`,
      request.url,
    ).toString();
    const body = {
      data: {
        upload_session_id: contractIds.uploadSessionId,
        material_id: contractIds.materialId,
        upload_url: uploadUrl,
        method: "PUT",
        required_headers: { "Content-Type": input.media_type },
        expires_at: "2099-12-31T23:59:59Z",
      },
      request_id: "contract_upload_session",
    } satisfies Schema<"UploadSessionEnvelope">;
    return HttpResponse.json(body, { status: 201 });
  }),

  // The upload URL is opaque object-storage transport returned by the runtime contract.
  http.put("*/__contract-upload/:uploadSessionId", () =>
    HttpResponse.text("", { headers: { ETag: '"contract-upload-etag"' }, status: 200 }),
  ),

  http.post(
    `${apiConfig.baseUrl}/projects/:projectId/materials/:materialId/confirm`,
    ({ request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      const body = {
        data: {
          job_id: contractIds.jobId,
          status: "queued",
          events_url: `${apiConfig.baseUrl}/generation-jobs/${contractIds.jobId}/events/stream`,
        },
        request_id: "contract_material_confirm",
      } satisfies Schema<"AcceptedJobEnvelope">;
      return HttpResponse.json(body, { status: 202 });
    },
  ),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/materials/:materialId/file-asset`, () => {
    const body = {
      data: contractFileAsset,
      request_id: "contract_material_file",
    } satisfies Schema<"FileAssetEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"file-asset-v1"' } });
  }),

  http.get(
    `${apiConfig.baseUrl}/projects/:projectId/materials/:materialId/parse-versions`,
    ({ request }) => {
      const item =
        scenario(request) === "failed"
          ? {
              ...contractParseVersion,
              status: "failed" as const,
              error_code: "PARSER_FAILED",
              completed_at: contractNow,
            }
          : contractParseVersion;
      const body = {
        data: { items: [item] },
        request_id: "contract_parse_versions",
      } satisfies Schema<"MaterialParseVersionListEnvelope">;
      return HttpResponse.json(body);
    },
  ),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/workflow`, ({ params, request }) => {
    const nodeStatus =
      scenario(request) === "running"
        ? "running"
        : scenario(request) === "partial"
          ? "partially_completed"
          : "review_required";
    const body = {
      data: {
        ...contractWorkflow,
        project: projectFixture(String(params.projectId)),
        node_runs: contractWorkflow.node_runs.map((node) => ({ ...node, status: nodeStatus })),
      },
      request_id: "contract_workflow",
    } satisfies Schema<"WorkflowEnvelope">;
    return HttpResponse.json(body);
  }),

  http.post(`${apiConfig.baseUrl}/projects/:projectId/artifacts`, async ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const input = (await request.json()) as Schema<"CreateArtifactRequest">;
    const artifact = {
      ...contractArtifact,
      project_id: String(params.projectId),
      lesson_unit_id: input.lesson_unit_id ?? null,
      branch_key: input.branch_key,
      artifact_key: input.artifact_key,
      artifact_type: input.artifact_type,
      content_definition_version_id: input.content_definition_version_id,
      current_draft: {
        ...contractArtifactDraft,
        draft_branch: input.draft_branch,
        content: input.content,
      },
    } satisfies Schema<"Artifact">;
    const body = {
      data: artifact,
      request_id: "contract_artifact_create",
    } satisfies Schema<"ArtifactEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"artifact-v2"' }, status: 201 });
  }),

  http.get(`${apiConfig.baseUrl}/artifacts/:artifactId`, ({ params, request }) => {
    if (scenario(request) === "not-found")
      return errorResponse("ARTIFACT_NOT_FOUND", "产物不存在", "contract_artifact_not_found", 404);
    const body = {
      data: { ...contractArtifact, id: String(params.artifactId) },
      request_id: "contract_artifact",
    } satisfies Schema<"ArtifactEnvelope">;
    return HttpResponse.json(body, { headers: { ETag: '"artifact-v2"' } });
  }),

  http.put(
    `${apiConfig.baseUrl}/artifacts/:artifactId/drafts/:draftBranch`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      if (scenario(request) === "conflict" || request.headers.get("If-Match") === '"stale"')
        return errorResponse(
          "EDIT_CONFLICT",
          "草稿已被其他修改覆盖",
          "contract_draft_conflict",
          409,
        );
      const input = (await request.json()) as Schema<"SaveArtifactDraftRequest">;
      const draft = {
        ...contractArtifactDraft,
        draft_branch: String(params.draftBranch),
        content: input.content,
        lock_version: contractArtifactDraft.lock_version + 1,
      } satisfies Schema<"ArtifactDraft">;
      const body = {
        data: draft,
        request_id: "contract_draft_save",
      } satisfies Schema<"ArtifactDraftEnvelope">;
      return HttpResponse.json(body, { headers: { ETag: '"artifact-v3"' } });
    },
  ),

  http.post(`${apiConfig.baseUrl}/artifacts/:artifactId/versions`, ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const body = {
      data: contractArtifactVersion,
      request_id: "contract_artifact_submit",
    } satisfies Schema<"ArtifactVersionEnvelope">;
    return HttpResponse.json(body, { status: 201 });
  }),

  http.post(
    `${apiConfig.baseUrl}/artifact-versions/:artifactVersionId/approvals`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      const input = (await request.json()) as Schema<"ReviewArtifactVersionRequest">;
      const body = {
        data: {
          id: "01970000-0000-7000-8000-000000000505",
          artifact_version_id: String(params.artifactVersionId),
          action: input.action,
          actor_type: "user",
          actor_user_id: contractIds.userId,
          comment: input.comment ?? null,
          quality_evidence: {},
          policy_snapshot: {},
          created_at: contractNow,
        },
        request_id: "contract_artifact_review",
      } satisfies Schema<"ApprovalEnvelope">;
      return HttpResponse.json(body, { status: 201 });
    },
  ),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/asset-slots`, ({ params, request }) => {
    const items =
      scenario(request) === "empty"
        ? []
        : [{ ...contractAssetSlot, project_id: String(params.projectId) }];
    const body = {
      data: { items },
      meta: { next_cursor: null },
      request_id: "contract_asset_slots",
    } satisfies Schema<"ProjectAssetSlotListEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/asset-package`, ({ params }) => {
    const projectId = String(params.projectId);
    const body = {
      data: { project_id: projectId, items: [{ ...contractAssetSlot, project_id: projectId }] },
      meta: { next_cursor: null },
      request_id: "contract_asset_package",
    } satisfies Schema<"ProjectAssetPackageEnvelope">;
    return HttpResponse.json(body);
  }),

  http.post(`${apiConfig.baseUrl}/asset-slots/:slotId/bindings`, async ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    if (scenario(request) === "conflict")
      return errorResponse(
        "TARGET_SLOT_OCCUPIED",
        "目标位置已有当前作品",
        "contract_binding_conflict",
        409,
      );
    const input = (await request.json()) as Schema<"BindAssetRequest">;
    const binding = {
      ...contractAssetBinding,
      project_asset_slot_id: String(params.slotId),
      file_asset_version_id: input.file_asset_version_id,
      source_artifact_version_id: input.source_artifact_version_id,
      position: input.position ?? 0,
    } satisfies Schema<"AssetBinding">;
    const body = {
      data: binding,
      request_id: "contract_asset_binding",
    } satisfies Schema<"AssetBindingEnvelope">;
    return HttpResponse.json(body, { status: 201 });
  }),

  http.post(`${apiConfig.baseUrl}/asset-bindings/:bindingId/unbind`, ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const binding = {
      ...contractAssetBinding,
      id: String(params.bindingId),
      is_active: false,
      unbound_at: contractNow,
      unbound_by: contractIds.userId,
    } satisfies Schema<"AssetBinding">;
    const body = {
      data: binding,
      request_id: "contract_asset_unbind",
    } satisfies Schema<"AssetBindingEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/node-runs/:nodeRunId/prompt-preview`, () => {
    const body = {
      data: {
        prompt_snapshot_id: "01970000-0000-7000-8000-000000000205",
        content_hash: "f".repeat(64),
        editable_prompt: "围绕当前已批准课时生成作品，保留学生发现和表达空间。",
        edit_policy: { mode: "replace_editable_layer", max_chars: 4_000 },
      },
      request_id: "contract_prompt_preview",
    } satisfies Schema<"PromptPreviewEnvelope">;
    return HttpResponse.json(body);
  }),

  http.post(`${apiConfig.baseUrl}/creation-batches`, async ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const input = (await request.json()) as Schema<"CreateCreationBatchRequest">;
    const itemId = contractPromptVersion.creation_item_id;
    const data: Schema<"CreationBatch"> =
      input.source_kind === "project"
        ? {
            id: "01970000-0000-7000-8000-000000000803",
            source_kind: "project",
            creation_package_id: input.creation_package_id,
            source: {
              project_id: contractIds.projectId,
              workflow_run_id: contractIds.workflowRunId,
              source_node_run_id: contractIds.nodeRunId,
            },
            studio_type: input.studio_type,
            title: input.title,
            status: "draft",
            items: [
              {
                id: itemId,
                item_key: "item-01",
                title: input.title,
                status: "draft",
                target_slot_key: "lesson.cover",
              },
            ],
          }
        : {
            id: "01970000-0000-7000-8000-000000000803",
            source_kind: "standalone",
            studio_type: input.studio_type,
            title: input.title,
            status: "draft",
            items: [],
          };
    const body = {
      data,
      request_id: "contract_creation_batch",
    } satisfies Schema<"CurrentCreationBatchEnvelope">;
    return HttpResponse.json(body, { status: 201 });
  }),

  http.post(
    `${apiConfig.baseUrl}/creation-items/:itemId/prompt-versions`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      const input = (await request.json()) as Schema<"SavePromptVersionRequest">;
      const promptVersion = {
        ...contractPromptVersion,
        creation_item_id: String(params.itemId),
        business_prompt: input.business_prompt,
        reference_asset_version_ids: input.reference_asset_version_ids,
        output_spec: input.output_spec,
        generation_profile: input.generation_profile,
      } satisfies Schema<"PromptVersion">;
      const body = {
        data: promptVersion,
        request_id: "contract_prompt_version",
      } satisfies Schema<"PromptVersionEnvelope">;
      return HttpResponse.json(body, { status: 201 });
    },
  ),

  http.post(`${apiConfig.baseUrl}/creation-items/:itemId/generate`, ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const body = {
      data: {
        job_id: contractIds.jobId,
        status: "queued",
        events_url: `${apiConfig.baseUrl}/generation-jobs/${contractIds.jobId}/events/stream`,
      },
      request_id: "contract_creation_generate",
    } satisfies Schema<"AcceptedJobEnvelope">;
    return HttpResponse.json(body, { status: 202 });
  }),

  http.post(`${apiConfig.baseUrl}/creation-batches/:batchId/generate`, ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const body = {
      data: {
        job_id: contractIds.jobId,
        status: "queued",
        events_url: `${apiConfig.baseUrl}/generation-jobs/${contractIds.jobId}/events/stream`,
      },
      request_id: "contract_batch_generate",
    } satisfies Schema<"AcceptedJobEnvelope">;
    return HttpResponse.json(body, { status: 202 });
  }),

  http.post(
    `${apiConfig.baseUrl}/generation-results/:resultId/adoptions`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      const input = (await request.json()) as Schema<"AdoptGenerationResultRequest">;
      const body = {
        data: {
          id: contractIds.adoptionId,
          creation_item_id: contractPromptVersion.creation_item_id,
          generation_result_id: String(params.resultId),
          adoption_mode: "teacher",
          reason: input.reason ?? null,
          adopted_at: contractNow,
        },
        request_id: "contract_adoption",
      } satisfies Schema<"AdoptionEnvelope">;
      return HttpResponse.json(body, { status: 201 });
    },
  ),

  http.post(
    `${apiConfig.baseUrl}/adoptions/:adoptionId/save-to-project`,
    async ({ params, request }) => {
      const rejected = requireCsrf(request);
      if (rejected) return rejected;
      const input = (await request.json()) as Schema<"SaveAdoptionToProjectRequest">;
      if (scenario(request) === "conflict")
        return errorResponse(
          "TARGET_SLOT_OCCUPIED",
          "目标位置已有当前作品",
          "contract_save_conflict",
          409,
        );
      const body = {
        data: {
          operation_id: "01970000-0000-7000-8000-000000000903",
          adoption_id: String(params.adoptionId),
          status: "completed",
          binding_id: contractIds.assetBindingId,
          target_project_id:
            input.source_kind === "standalone" ? input.project_id : contractIds.projectId,
          target_slot_key:
            input.source_kind === "standalone" ? input.slot_key : contractAssetSlot.slot_key,
          idempotent_replay: false,
        },
        request_id: "contract_save_adoption",
      } satisfies Schema<"SaveToProjectOperationEnvelope">;
      return HttpResponse.json(body);
    },
  ),

  http.post(`${apiConfig.baseUrl}/generation-results/:resultId/save-to-project`, ({ request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const body = {
      data: {
        operation_id: "01970000-0000-7000-8000-000000000904",
        status: "completed",
        binding_id: contractIds.assetBindingId,
      },
      request_id: "contract_legacy_save",
    } satisfies Schema<"SaveOperationEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/generation-jobs/:jobId`, ({ params, request }) => {
    const state = scenario(request);
    const status =
      state === "failed"
        ? "failed"
        : state === "cancelled"
          ? "cancelled"
          : state === "running"
            ? "running"
            : contractJob.status;
    const job = {
      ...contractJob,
      id: String(params.jobId),
      status,
      progress_percent: status === "running" ? 62 : status === "succeeded" ? 100 : 0,
      progress_message:
        status === "failed"
          ? "教材解析未完成"
          : status === "running"
            ? "正在解析教材"
            : contractJob.progress_message,
      error_code: status === "failed" ? "MATERIAL_PARSE_FAILED" : null,
    } satisfies Schema<"GenerationJob">;
    const body = {
      data: job,
      request_id: "contract_job",
    } satisfies Schema<"GenerationJobEnvelope">;
    return HttpResponse.json(body);
  }),

  http.post(`${apiConfig.baseUrl}/generation-jobs/:jobId/cancel`, ({ params, request }) => {
    const rejected = requireCsrf(request);
    if (rejected) return rejected;
    const job = {
      ...contractJob,
      id: String(params.jobId),
      status: "cancel_requested",
      progress_message: "正在取消任务",
    } satisfies Schema<"GenerationJob">;
    const body = {
      data: job,
      request_id: "contract_job_cancel",
    } satisfies Schema<"GenerationJobEnvelope">;
    return HttpResponse.json(body);
  }),

  http.get(`${apiConfig.baseUrl}/generation-jobs/:jobId/events/stream`, ({ params, request }) =>
    contractSse(
      request,
      "generation.job.updated",
      { id: String(params.jobId), type: "generation_job" },
      contractIds.projectId,
      { status: "succeeded", progress_percent: 100 },
    ),
  ),

  http.get(`${apiConfig.baseUrl}/projects/:projectId/events/stream`, ({ params, request }) =>
    contractSse(
      request,
      "project.updated",
      { id: String(params.projectId), type: "project" },
      String(params.projectId),
      { updated_at: contractNow },
    ),
  ),
];
