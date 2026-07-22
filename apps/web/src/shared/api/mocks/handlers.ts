import { delay, http, HttpResponse } from "msw";
import { apiConfig } from "@/shared/api/config";
import {
  mockEnvelope as envelope,
  mockIntroOptions as introOptions,
  mockNow as now,
} from "@/shared/api/mocks/fixtures";
import {
  createMockTask,
  createMockProject,
  getMockProject,
  getMockRuntimeState,
  saveMockDraft,
  updateMockTask,
  updateMockProject,
} from "@/shared/api/mocks/runtime";
import {
  getApprovedProjectLessons,
  isApprovedLessonId,
} from "@/features/workbench/lib/projectLessons";

const introOptionSetVersionId = "01960000-0000-7000-8000-000000000301";
type CreationPackageRecord = {
  lessonId: string;
  nodeRevision: number;
  nodeRunId: string;
  packageType: string;
  projectId: string;
  replaceMode: string;
  targetSlotKey: string;
};

type CreationBatchRecord = {
  itemIds: string[];
  packageId?: string;
  studioType: string;
  projectId?: string;
  lessonId?: string;
};

type GenerationResultRecord = {
  batchId: string;
  packageId?: string;
  projectId?: string;
  lessonId?: string;
};

type GenerationJobRecord = {
  batchId: string;
  projectId?: string;
  resultIds: string[];
};

type CreationContractState = {
  batches: Record<string, CreationBatchRecord>;
  jobs: Record<string, GenerationJobRecord>;
  packages: Record<string, CreationPackageRecord>;
  results: Record<string, GenerationResultRecord>;
};

const creationContractStateKey = "mock:creation-contract-state";

function readCreationContractState(): CreationContractState {
  const value = getMockRuntimeState().drafts[creationContractStateKey]?.value as
    Partial<CreationContractState> | undefined;
  return {
    batches: value?.batches ?? {},
    jobs: value?.jobs ?? {},
    packages: value?.packages ?? {},
    results: value?.results ?? {},
  };
}

function updateCreationContractState(
  updater: (state: CreationContractState) => CreationContractState,
) {
  return saveMockDraft(creationContractStateKey, updater(readCreationContractState()));
}

function errorResponse(
  code: string,
  message: string,
  requestId: string,
  status: 404 | 409 | 422 = 404,
) {
  return HttpResponse.json(
    {
      error: { code, message, retryable: false },
      request_id: requestId,
    },
    { status },
  );
}

function findNodeRun(nodeRunId: string) {
  return Object.values(getMockRuntimeState().nodeStates).find((node) => node.id === nodeRunId);
}

function packageSourceIsCurrent(packageRecord: CreationPackageRecord) {
  const node = findNodeRun(packageRecord.nodeRunId);
  return (
    node?.project_id === packageRecord.projectId &&
    node.lesson_id === packageRecord.lessonId &&
    node.revision === packageRecord.nodeRevision &&
    node.status === "approved"
  );
}

function sseResponse(
  eventType: string,
  resource: { id: string; type: string },
  payload: Record<string, unknown>,
  projectId: string | null,
) {
  const eventId = crypto.randomUUID();
  const data = {
    event_id: eventId,
    sequence_no: 1,
    event_type: eventType,
    occurred_at: now,
    project_id: projectId,
    resource,
    payload,
    request_id: null,
  };
  return new HttpResponse(`id: 1\nevent: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
  });
}

export const handlers = [
  http.get(`${apiConfig.baseUrl}/health`, () =>
    HttpResponse.json(envelope({ status: "ok" }, "req_mock_health")),
  ),
  http.get(`${apiConfig.baseUrl}/projects`, async () => {
    await delay(80);
    return HttpResponse.json({
      data: { items: getMockRuntimeState().projects },
      meta: { next_cursor: null },
      request_id: "req_mock_projects",
    });
  }),
  http.post(`${apiConfig.baseUrl}/projects`, async ({ request }) => {
    const body = (await request.json()) as {
      title: string;
      knowledge_point: string;
      grade?: string | null;
      textbook_edition?: string | null;
      automation_mode?: "manual" | "assisted" | "automatic";
    };
    const project = createMockProject(body);
    return HttpResponse.json(envelope(project, "req_mock_create_project"), { status: 201 });
  }),
  http.get(`${apiConfig.baseUrl}/projects/:projectId`, ({ params }) => {
    const project = getMockProject(String(params.projectId));
    if (!project) {
      return HttpResponse.json(
        {
          error: {
            code: "PROJECT_NOT_FOUND",
            message: "项目不存在",
            retryable: false,
          },
          request_id: "req_mock_project_not_found",
        },
        { status: 404 },
      );
    }
    return HttpResponse.json(envelope(project, "req_mock_project"), {
      headers: { ETag: '"project-v3"' },
    });
  }),
  http.patch(`${apiConfig.baseUrl}/projects/:projectId`, async ({ params, request }) => {
    const body = (await request.json()) as {
      title?: string;
      knowledge_point?: string;
      grade?: string | null;
      textbook_edition?: string | null;
      automation_mode?: "manual" | "assisted" | "automatic";
    };
    const project = updateMockProject(String(params.projectId), body);
    if (!project) {
      return HttpResponse.json(
        {
          error: {
            code: "PROJECT_NOT_FOUND",
            message: "项目不存在",
            retryable: false,
          },
          request_id: "req_mock_update_project_not_found",
        },
        { status: 404 },
      );
    }
    return HttpResponse.json(envelope(project, "req_mock_update_project"));
  }),
  http.get(`${apiConfig.baseUrl}/projects/:projectId/workflow`, ({ params, request }) => {
    const scenario = new URL(request.url).searchParams.get("scenario");
    const projectId = String(params.projectId);
    const project = getMockProject(projectId);
    if (!project) {
      return HttpResponse.json(
        {
          error: {
            code: "PROJECT_NOT_FOUND",
            message: "项目不存在",
            retryable: false,
          },
          request_id: "req_mock_workflow_project_not_found",
        },
        { status: 404 },
      );
    }
    const runtime = getMockRuntimeState();
    const projectLessons = getApprovedProjectLessons(runtime, projectId).map(({ id, title }) => ({
      id,
      title,
    }));
    const lessonPlanStatus =
      scenario === "node_running"
        ? "running"
        : scenario === "node_partial"
          ? "partially_completed"
          : scenario === "node_stale"
            ? "stale"
            : "review_required";
    const nodeRuns = Object.values(runtime.nodeStates)
      .filter((node) => node.project_id === projectId)
      .map((node) => ({
        id: node.id,
        node_key: node.node_key,
        stale_reason: node.stale_reason,
        status: node.status,
        title: node.title,
      }));
    const scenarioNode = nodeRuns.find((node) => node.node_key === "lesson-plan");
    if (scenarioNode && scenario) {
      scenarioNode.status = lessonPlanStatus;
      scenarioNode.stale_reason =
        scenario === "node_stale" ? { summary: "课时范围已批准新版本" } : null;
    }
    return HttpResponse.json(
      envelope(
        {
          project,
          lessons: projectLessons,
          node_runs: nodeRuns,
        },
        "req_mock_workflow",
      ),
    );
  }),
  http.get(`${apiConfig.baseUrl}/lessons/:lessonId/intro-options`, ({ params }) => {
    const lessonId = String(params.lessonId);
    const runtime = getMockRuntimeState();
    if (!isApprovedLessonId(runtime, lessonId)) {
      return HttpResponse.json(
        {
          error: { code: "LESSON_NOT_FOUND", message: "课时不存在", retryable: false },
          request_id: "req_mock_intro_lesson_not_found",
        },
        { status: 404 },
      );
    }
    return HttpResponse.json(
      envelope(
        {
          option_set_id: introOptionSetVersionId,
          lesson_unit_id: lessonId,
          status: "review_required",
          ideation_context_snapshot_id: "01960000-0000-7000-8000-000000000302",
          anchoring_context_snapshot_id: "01960000-0000-7000-8000-000000000303",
          options: introOptions,
          created_at: now,
        },
        "req_mock_intro_options",
      ),
    );
  }),
  http.post(
    `${apiConfig.baseUrl}/lessons/:lessonId/intro-selections`,
    async ({ params, request }) => {
      const lessonId = String(params.lessonId);
      const runtime = getMockRuntimeState();
      if (!isApprovedLessonId(runtime, lessonId)) {
        return HttpResponse.json(
          {
            error: { code: "LESSON_NOT_FOUND", message: "课时不存在", retryable: false },
            request_id: "req_mock_intro_selection_lesson_not_found",
          },
          { status: 404 },
        );
      }
      const body = (await request.json()) as {
        intro_option_set_version_id: string;
        option_key: string;
      };
      if (
        body.intro_option_set_version_id !== introOptionSetVersionId ||
        !introOptions.some((option) => option.option_key === body.option_key)
      ) {
        return errorResponse(
          "INTRO_OPTION_NOT_FOUND",
          "课堂导入方案不属于当前方案集",
          "req_mock_intro_selection_invalid_option",
          422,
        );
      }
      return HttpResponse.json(
        envelope(
          {
            selection_id: crypto.randomUUID(),
            option_set_version_id: body.intro_option_set_version_id,
            option_key: body.option_key,
            choice_mode: "teacher_selected",
            selected_at: now,
          },
          "req_mock_intro_selection",
        ),
        { status: 201 },
      );
    },
  ),
  http.get(`${apiConfig.baseUrl}/node-runs/:nodeRunId/prompt-preview`, ({ params }) => {
    const nodeRunId = String(params.nodeRunId);
    const node = findNodeRun(nodeRunId);
    if (!node) {
      return errorResponse(
        "NODE_RUN_NOT_FOUND",
        "制作步骤不存在",
        "req_mock_prompt_node_not_found",
      );
    }
    const project = getMockProject(node.project_id);
    return HttpResponse.json(
      envelope(
        {
          editable_prompt: `围绕${project?.knowledge_point ?? "当前已批准课时"}生成当前作品，保留学生发现和表达空间。`,
          locked_layers: [{ title: "儿童安全" }, { title: "输出结构" }],
          context_summary: [{ title: "批准课时范围" }, { title: "教材证据" }],
          schema: null,
        },
        "req_mock_prompt",
      ),
    );
  }),
  http.post(`${apiConfig.baseUrl}/node-runs/:nodeRunId/start`, ({ params }) => {
    const nodeRunId = String(params.nodeRunId);
    const node = findNodeRun(nodeRunId);
    if (!node) {
      return errorResponse("NODE_RUN_NOT_FOUND", "制作步骤不存在", "req_mock_start_node_not_found");
    }
    if (node.status !== "approved") {
      return errorResponse(
        "NODE_RUN_NOT_APPROVED",
        "当前步骤尚未批准，不能开始制作",
        "req_mock_start_node_not_approved",
        409,
      );
    }
    return HttpResponse.json(
      envelope(
        {
          job_id: crypto.randomUUID(),
          status: "queued",
          events_url: `${apiConfig.baseUrl}/projects/${node.project_id}/events/stream`,
        },
        "req_mock_start",
      ),
      { status: 202 },
    );
  }),
  http.post(`${apiConfig.baseUrl}/node-runs/:nodeRunId/creation-packages`, ({ params }) => {
    const nodeRunId = String(params.nodeRunId);
    const node = findNodeRun(nodeRunId);
    if (!node?.lesson_id) {
      return errorResponse(
        "NODE_RUN_NOT_FOUND",
        "课时制作步骤不存在",
        "req_mock_package_node_not_found",
      );
    }
    if (node.status !== "approved") {
      return errorResponse(
        "NODE_RUN_NOT_APPROVED",
        "当前步骤尚未批准，不能创建创作包",
        "req_mock_package_node_not_approved",
        409,
      );
    }
    const project = getMockProject(node.project_id);
    const packageId = crypto.randomUUID();
    const lessonId = node.lesson_id;
    updateCreationContractState((state) => ({
      ...state,
      packages: {
        ...state.packages,
        [packageId]: {
          lessonId,
          nodeRevision: node.revision,
          nodeRunId,
          packageType: "image",
          projectId: node.project_id,
          replaceMode: "reject_if_occupied",
          targetSlotKey: "video.asset.primary",
        },
      },
    }));
    return HttpResponse.json(
      envelope(
        {
          package_id: packageId,
          package_type: "image",
          status: "ready",
          source: {
            project_id: node.project_id,
            lesson_unit_id: node.lesson_id,
            node_run_id: nodeRunId,
            is_stale: false,
          },
          style_contract: { title: "温和课堂视觉" },
          items: [
            {
              item_key: "VIDEO-ASSET-01",
              position: 1,
              title: `${project?.knowledge_point ?? "当前课时"}关键画面`,
              prompt: { content: "制作清晰、适龄、无水印的课堂画面素材" },
              reference_assets: [],
              output_spec: { aspect_ratio: "1:1" },
              target_slot_key: "video.asset.primary",
              consistency_key: `video-style-${node.project_id}`,
            },
          ],
          target_rules: { replace_mode: "reject_if_occupied" },
          created_at: now,
        },
        "req_mock_package",
      ),
      { status: 201 },
    );
  }),
  http.post(`${apiConfig.baseUrl}/creation-batches`, async ({ request }) => {
    const body = (await request.json()) as {
      creation_package_id?: string | null;
      studio_type?: string;
      title?: string;
    };
    if (
      !body.title?.trim() ||
      !body.studio_type ||
      !["image", "video", "presentation"].includes(body.studio_type)
    ) {
      return errorResponse(
        "INVALID_CREATION_BATCH",
        "创作批次信息不完整",
        "req_mock_batch_invalid",
        422,
      );
    }
    const packageRecord = body.creation_package_id
      ? readCreationContractState().packages[body.creation_package_id]
      : undefined;
    if (body.creation_package_id && !packageRecord) {
      return errorResponse(
        "CREATION_PACKAGE_NOT_FOUND",
        "创作包不存在",
        "req_mock_batch_package_not_found",
      );
    }
    if (packageRecord && !packageSourceIsCurrent(packageRecord)) {
      return errorResponse(
        "STALE_CREATION_PACKAGE",
        "来源内容已经更新，请重新创建创作包",
        "req_mock_batch_stale_package",
        409,
      );
    }
    if (packageRecord && packageRecord.packageType !== body.studio_type) {
      return errorResponse(
        "CREATION_PACKAGE_TYPE_MISMATCH",
        "创作包类型与创作台不一致",
        "req_mock_batch_type_mismatch",
        422,
      );
    }
    const batchId = crypto.randomUUID();
    const itemId = crypto.randomUUID();
    const studioType = body.studio_type;
    updateCreationContractState((state) => ({
      ...state,
      batches: {
        ...state.batches,
        [batchId]: {
          itemIds: [itemId],
          packageId: body.creation_package_id ?? undefined,
          studioType,
          projectId: packageRecord?.projectId,
          lessonId: packageRecord?.lessonId,
        },
      },
    }));
    return HttpResponse.json(
      envelope(
        {
          id: batchId,
          studio_type: body.studio_type,
          title: body.title.trim(),
          status: "ready",
          items: [{ id: itemId }],
        },
        "req_mock_batch",
      ),
      { status: 201 },
    );
  }),
  http.post(
    `${apiConfig.baseUrl}/creation-batches/:batchId/generate`,
    async ({ params, request }) => {
      const batchId = String(params.batchId);
      const contractState = readCreationContractState();
      const batch = contractState.batches[batchId];
      if (!batch) {
        return errorResponse(
          "CREATION_BATCH_NOT_FOUND",
          "创作批次不存在",
          "req_mock_generate_batch_not_found",
        );
      }
      const packageRecord = batch.packageId ? contractState.packages[batch.packageId] : undefined;
      if (batch.packageId && (!packageRecord || !packageSourceIsCurrent(packageRecord))) {
        return errorResponse(
          "STALE_CREATION_PACKAGE",
          "来源内容已经更新，请重新创建创作包",
          "req_mock_generate_stale_package",
          409,
        );
      }
      const body = (await request.json()) as { item_ids?: string[] };
      if (
        !Array.isArray(body.item_ids) ||
        body.item_ids.length === 0 ||
        body.item_ids.some((itemId) => !batch.itemIds.includes(itemId))
      ) {
        return errorResponse(
          "CREATION_ITEM_NOT_FOUND",
          "待生成项目不属于当前批次",
          "req_mock_generate_item_not_found",
          422,
        );
      }
      const resultIds = body.item_ids.map(() => crypto.randomUUID());
      const job = createMockTask({
        detail: "创作台生成任务",
        progress: 0,
        project_id: batch.projectId ?? null,
        stage: "等待生成",
        status: "queued",
        title: "生成课堂素材",
      });
      const jobId = job.id;
      updateCreationContractState((state) => ({
        ...state,
        jobs: { ...state.jobs, [jobId]: { batchId, projectId: batch.projectId, resultIds } },
        results: {
          ...state.results,
          ...Object.fromEntries(
            resultIds.map((resultId) => [
              resultId,
              {
                batchId,
                packageId: batch.packageId,
                projectId: batch.projectId,
                lessonId: batch.lessonId,
              },
            ]),
          ),
        },
      }));
      return HttpResponse.json(
        envelope(
          {
            job_id: jobId,
            status: "queued",
            events_url: `${apiConfig.baseUrl}/generation-jobs/${jobId}/events/stream`,
          },
          "req_mock_generate",
        ),
        { status: 202 },
      );
    },
  ),
  http.post(
    `${apiConfig.baseUrl}/generation-results/:resultId/save-to-project`,
    async ({ params, request }) => {
      const resultId = String(params.resultId);
      const contractState = readCreationContractState();
      const result = contractState.results[resultId];
      const batch = result ? contractState.batches[result.batchId] : undefined;
      if (!result || !batch) {
        return errorResponse(
          "GENERATION_RESULT_NOT_FOUND",
          "生成结果不存在",
          "req_mock_save_result_not_found",
        );
      }
      const body = (await request.json()) as {
        project_id?: string;
        replace_mode?: string;
        slot_key?: string;
      };
      if (!body.project_id || !getMockProject(body.project_id)) {
        return errorResponse(
          "PROJECT_NOT_FOUND",
          "目标项目不存在",
          "req_mock_save_project_not_found",
        );
      }
      if (result.projectId && result.projectId !== body.project_id) {
        return errorResponse(
          "SOURCE_PROJECT_MISMATCH",
          "生成结果只能保存回来源项目",
          "req_mock_save_source_project_mismatch",
          409,
        );
      }
      const packageRecord = result.packageId ? contractState.packages[result.packageId] : undefined;
      if (result.packageId && (!packageRecord || !packageSourceIsCurrent(packageRecord))) {
        return errorResponse(
          "STALE_CREATION_PACKAGE",
          "来源内容已经更新，请重新制作后再保存",
          "req_mock_save_stale_package",
          409,
        );
      }
      if (
        !body.slot_key?.trim() ||
        !body.replace_mode ||
        !["reject_if_occupied", "replace_active", "append"].includes(body.replace_mode)
      ) {
        return errorResponse(
          "INVALID_SAVE_TARGET",
          "保存位置或替换方式无效",
          "req_mock_save_invalid_target",
          422,
        );
      }
      if (
        packageRecord &&
        (body.slot_key !== packageRecord.targetSlotKey ||
          body.replace_mode !== packageRecord.replaceMode)
      ) {
        return errorResponse(
          "SAVE_TARGET_MISMATCH",
          "保存位置或替换方式与创作包不一致",
          "req_mock_save_target_mismatch",
          422,
        );
      }
      if (body.replace_mode === "reject_if_occupied") {
        return HttpResponse.json(
          {
            error: {
              code: "TARGET_SLOT_OCCUPIED",
              message: "目标位置已有当前作品",
              retryable: false,
              details: { current_version: "v2" },
            },
            request_id: "req_mock_save_conflict",
          },
          { status: 409 },
        );
      }
      return HttpResponse.json(
        envelope(
          {
            operation_id: crypto.randomUUID(),
            status: "completed",
            binding_id: crypto.randomUUID(),
          },
          "req_mock_save",
        ),
      );
    },
  ),
  http.get(`${apiConfig.baseUrl}/projects/:projectId/events/stream`, ({ params }) => {
    if (!getMockProject(String(params.projectId))) {
      return errorResponse("PROJECT_NOT_FOUND", "项目不存在", "req_mock_events_project_not_found");
    }
    const projectId = String(params.projectId);
    return sseResponse(
      "project.created",
      { id: projectId, type: "project" },
      { status: "running" },
      projectId,
    );
  }),
  http.get(`${apiConfig.baseUrl}/generation-jobs/:jobId/events/stream`, ({ params }) => {
    const jobId = String(params.jobId);
    const contractState = readCreationContractState();
    const job = contractState.jobs[jobId];
    const task = getMockRuntimeState().tasks.find((candidate) => candidate.id === jobId);
    if (!job || !task) {
      return errorResponse(
        "GENERATION_JOB_NOT_FOUND",
        "生成任务不存在",
        "req_mock_generation_events_not_found",
      );
    }
    updateMockTask(jobId, {
      progress: 100,
      stage: "等待确认",
      status: "review_required",
    });
    return sseResponse(
      "generation.job.progress",
      { id: jobId, type: "generation_job" },
      { result_ids: job.resultIds, status: "succeeded" },
      job.projectId ?? null,
    );
  }),
];
