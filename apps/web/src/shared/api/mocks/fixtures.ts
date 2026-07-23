import type { components } from "@/generated/api-schema";

type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

export const contractNow = "2026-07-22T08:30:00Z";

export const contractIds = {
  adoptionId: "01970000-0000-7000-8000-000000000901",
  artifactDraftId: "01970000-0000-7000-8000-000000000502",
  artifactId: "01970000-0000-7000-8000-000000000501",
  artifactVersionId: "01970000-0000-7000-8000-000000000503",
  assetBindingId: "01970000-0000-7000-8000-000000000702",
  assetSlotId: "01970000-0000-7000-8000-000000000701",
  contentDefinitionVersionId: "01970000-0000-7000-8000-000000000504",
  contentReleaseId: "01970000-0000-7000-8000-000000000202",
  fileAssetId: "01970000-0000-7000-8000-000000000401",
  fileAssetVersionId: "01970000-0000-7000-8000-000000000402",
  generationResultId: "01970000-0000-7000-8000-000000000902",
  jobId: "01970000-0000-7000-8000-000000000301",
  lessonId: "01960000-0000-7000-8000-000000000101",
  materialId: "01970000-0000-7000-8000-000000000302",
  nodeRunId: "01970000-0000-7000-8000-000000000204",
  parseVersionId: "01970000-0000-7000-8000-000000000403",
  projectId: "01960000-0000-7000-8000-000000000001",
  promptVersionId: "01970000-0000-7000-8000-000000000802",
  sourceDivisionVersionId: "01970000-0000-7000-8000-000000000102",
  uploadSessionId: "01970000-0000-7000-8000-000000000303",
  userId: "01970000-0000-7000-8000-000000000601",
  workflowDefinitionVersionId: "01970000-0000-7000-8000-000000000201",
  workflowRunId: "01970000-0000-7000-8000-000000000203",
} as const;

export const contractProject = {
  id: contractIds.projectId,
  title: "认识百分数",
  subject: "primary_math",
  grade: "六年级",
  textbook_edition: "人教版",
  knowledge_point: "百分数的意义与读写",
  status: "active",
  execution_mode: "guided",
  content_release_id: contractIds.contentReleaseId,
  workflow_definition_version_id: contractIds.workflowDefinitionVersionId,
  created_at: "2026-07-20T02:00:00Z",
  updated_at: contractNow,
} satisfies Schema<"CurrentProject">;

export const contractAutomationPolicy = {
  project_id: contractIds.projectId,
  workflow_definition_version_id: contractIds.workflowDefinitionVersionId,
  mode: "guided",
  node_rules: [
    {
      node_key: "lesson-plan",
      auto_start: false,
      auto_submit: false,
      auto_approve: false,
      pause_after: true,
    },
  ],
  policy_version: 3,
  updated_at: contractNow,
} satisfies Schema<"AutomationPolicy">;

export const contractLesson = {
  id: contractIds.lessonId,
  project_id: contractIds.projectId,
  lesson_key: "lesson-01",
  position: 1,
  title: "百分数的意义",
  scope_summary: "从生活情境理解百分数表示两个量之间的关系。",
  objective_summary: "能读写百分数，并解释百分数在具体情境中的意义。",
  estimated_minutes: 40,
  source_division_version_id: contractIds.sourceDivisionVersionId,
  status: "active",
  lock_version: 2,
  branches: [
    { branch_key: "lesson_plan", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "intro_options", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "ppt", enabled: true, workflow_status: "not_ready", settings: {} },
    { branch_key: "video", enabled: false, workflow_status: "disabled", settings: {} },
  ],
  created_at: "2026-07-21T03:00:00Z",
  updated_at: contractNow,
} satisfies Schema<"Lesson">;

export const contractWorkflow = {
  project: contractProject,
  workflow_run: {
    id: contractIds.workflowRunId,
    run_no: 1,
    status: "active",
    content_release_id: contractIds.contentReleaseId,
    workflow_definition_version_id: contractIds.workflowDefinitionVersionId,
    started_at: "2026-07-21T03:00:00Z",
    completed_at: null,
  },
  lessons: [],
  node_runs: [
    {
      id: contractIds.nodeRunId,
      workflow_run_id: contractIds.workflowRunId,
      branch_run_id: null,
      node_key: "lesson-plan",
      run_no: 1,
      status: "review_required",
      title: "教案",
      stale_reason: null,
      started_at: "2026-07-22T08:00:00Z",
      finished_at: null,
    },
  ],
} satisfies Schema<"WorkflowEnvelope">["data"];

export const contractFileAsset = {
  id: contractIds.fileAssetId,
  asset_key: "source-material",
  asset_kind: "document",
  status: "active",
  retention_class: "project_source",
  lock_version: 1,
  current_version: {
    id: contractIds.fileAssetVersionId,
    version_no: 1,
    mime_type: "application/pdf",
    byte_size: 524_288,
    sha256: "b".repeat(64),
    width: null,
    height: null,
    duration_ms: null,
    page_count: 18,
    scan_status: "clean",
    derived_from_version_id: null,
    created_at: contractNow,
  },
} satisfies Schema<"FileAsset">;

export const contractParseVersion = {
  id: contractIds.parseVersionId,
  source_material_id: contractIds.materialId,
  file_asset_version_id: contractIds.fileAssetVersionId,
  generation_job_id: contractIds.jobId,
  version_no: 1,
  status: "succeeded",
  parser_name: "document-parser",
  parser_version: "1.0",
  page_count: 18,
  text_checksum: "c".repeat(64),
  validation_report: {},
  error_code: null,
  created_at: "2026-07-22T08:00:00Z",
  started_at: "2026-07-22T08:01:00Z",
  completed_at: contractNow,
} satisfies Schema<"MaterialParseVersion">;

export const contractJob = {
  id: contractIds.jobId,
  project_id: contractIds.projectId,
  job_type: "material.parse",
  status: "succeeded",
  progress_percent: 100,
  progress_message: "教材已经解析完成",
  error_code: null,
  created_at: "2026-07-22T08:00:00Z",
  updated_at: contractNow,
} satisfies Schema<"GenerationJob">;

export const contractAssetBinding = {
  id: contractIds.assetBindingId,
  project_asset_slot_id: contractIds.assetSlotId,
  file_asset_version_id: contractIds.fileAssetVersionId,
  source_artifact_version_id: null,
  position: 0,
  is_active: true,
  bound_at: contractNow,
  bound_by: contractIds.userId,
  unbound_at: null,
  unbound_by: null,
} satisfies Schema<"AssetBinding">;

export const contractAssetSlot = {
  id: contractIds.assetSlotId,
  project_id: contractIds.projectId,
  lesson_unit_id: contractIds.lessonId,
  slot_key: "lesson.cover",
  asset_type: "image",
  cardinality: "one",
  required: false,
  status: "satisfied",
  target_contract: {
    allowed_mime_types: ["image/png", "image/jpeg"],
    require_clean_scan: true,
  },
  active_bindings: [contractAssetBinding],
} satisfies Schema<"ProjectAssetSlot">;

export const contractArtifactDraft = {
  id: contractIds.artifactDraftId,
  draft_branch: "main",
  content: {},
  validation_report: {},
  based_on_version_id: null,
  autosaved_at: contractNow,
  lock_version: 2,
} satisfies Schema<"ArtifactDraft">;

export const contractArtifactVersion = {
  id: contractIds.artifactVersionId,
  version_no: 1,
  content: {},
  content_hash: "d".repeat(64),
  render_summary: {},
  source_kind: "manual",
  source_node_run_id: null,
  context_snapshot_id: null,
  prompt_snapshot_id: null,
  validation_report: {},
  created_at: contractNow,
  created_by: contractIds.userId,
} satisfies Schema<"ArtifactVersion">;

export const contractArtifact = {
  id: contractIds.artifactId,
  project_id: contractIds.projectId,
  lesson_unit_id: contractIds.lessonId,
  branch_key: "lesson_plan",
  artifact_key: "lesson-plan",
  artifact_type: "lesson_plan",
  content_definition_version_id: contractIds.contentDefinitionVersionId,
  status: "draft",
  stale_reason: null,
  lock_version: 2,
  current_draft: contractArtifactDraft,
  current_submitted_version: null,
  current_approved_version: null,
  created_at: "2026-07-22T08:00:00Z",
  updated_at: contractNow,
} satisfies Schema<"Artifact">;

export const contractPromptVersion = {
  id: contractIds.promptVersionId,
  creation_item_id: "01970000-0000-7000-8000-000000000801",
  version_no: 1,
  business_prompt: "为课堂制作一张清晰、适龄的百分数情境图。",
  reference_asset_version_ids: [],
  output_spec: {},
  generation_profile: "balanced",
  content_hash: "e".repeat(64),
  created_at: contractNow,
} satisfies Schema<"PromptVersion">;

export function projectFixture(id: string = contractIds.projectId): Schema<"CurrentProject"> {
  return { ...contractProject, id };
}

export function lessonFixture(
  id: string = contractIds.lessonId,
  projectId: string = contractIds.projectId,
): Schema<"Lesson"> {
  return { ...contractLesson, id, project_id: projectId };
}
