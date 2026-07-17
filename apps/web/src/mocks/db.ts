import type {
  ContentDefinition,
} from "@/entities/content/definition";
import type { IntroOptionSet } from "@/entities/content/introOptions";
import type { PptPageSpec } from "@/entities/content/pptPage";
import type { VideoShot } from "@/entities/content/videoShot";

/**
 * Mock 内存数据库。
 * 只在 mock 模式与测试中存在；页面与业务组件不感知本模块。
 * 所有可编辑资源携带 etag 计数，实现 If-Match / 409 EDIT_CONFLICT。
 */

export interface MockUser {
  id: string;
  name: string;
  email: string;
  password: string;
  roles: ("teacher" | "content_admin" | "model_admin" | "system_admin")[];
}

export interface MockProject {
  id: string;
  title: string;
  knowledge_point: string;
  grade: string | null;
  textbook_edition: string | null;
  status: "draft" | "active" | "archived";
  automation_mode: "manual" | "assisted" | "automatic";
  created_at: string;
  updated_at: string;
  etag: number;
}

export interface MockMaterial {
  id: string;
  project_id: string;
  status: "uploading" | "scanning" | "parsing" | "parsed" | "scope_confirmed" | "failed";
  file_name: string | null;
  page_count: number | null;
  knowledge_scope: string | null;
  evidence: { page_no: number; summary: string; excerpt?: string | null }[];
  failure_reason: string | null;
  uploaded_at: string | null;
}

export interface MockDivisionEntry {
  entry_id: string;
  position: number;
  title: string;
  focus: string;
  duration_minutes: number | null;
  lesson_id: string | null;
}

export interface MockDivision {
  project_id: string;
  status: "not_ready" | "draft" | "review_required" | "approved";
  source_evidence_note: string | null;
  entries: MockDivisionEntry[];
  etag: number;
}

export interface MockBranch {
  state:
    | "disabled"
    | "skipped"
    | "not_ready"
    | "in_progress"
    | "review_required"
    | "approved"
    | "stale"
    | "failed";
  summary: string | null;
  next_step_key: string | null;
}

export interface MockLesson {
  id: string;
  project_id: string;
  position: number;
  title: string;
  focus: string | null;
  duration_minutes: number | null;
  branches: {
    lesson_plan: MockBranch;
    intro_options: MockBranch;
    ppt: MockBranch;
    video: MockBranch;
  };
  updated_at: string;
  etag: number;
}

export interface MockNodeRun {
  id: string;
  lesson_id: string | null;
  project_id: string;
  node_key: string;
  title: string;
  status: string;
  current_artifact_version_id: string | null;
  active_job_id: string | null;
  skippable: boolean;
  stale_reason: Record<string, unknown> | null;
  updated_at: string;
}

export interface MockArtifactVersion {
  id: string;
  node_run_id: string;
  kind: string;
  review_status: "draft" | "review_required" | "approved" | "rejected" | "superseded";
  version_no: number;
  is_current: boolean;
  content: Record<string, unknown>;
  content_definition_version_id: string | null;
  validation_issues: {
    key: string;
    severity: "error" | "warning" | "info";
    message: string;
    field_path?: string | null;
  }[];
  source: "generated" | "teacher_edited" | "imported";
  created_at: string;
  approved_at: string | null;
  approval_note: string | null;
  etag: number;
}

export interface MockPrompt {
  node_run_id: string;
  editable_prompt: string;
  default_prompt: string;
  prompt_revision_id: string | null;
  locked_layers: { title: string; summary: string }[];
  context_summary: { title: string; detail: string }[];
  etag: number;
}

export interface MockIntroSelection {
  selection_id: string;
  lesson_id: string;
  option_set_version_id: string;
  option_key: string;
  choice_mode: "teacher_selected" | "policy_default";
  selected_at: string;
}

export interface MockPptPage {
  page_id: string;
  lesson_id: string;
  spec: PptPageSpec;
  status: "draft" | "generating" | "review_required" | "approved" | "stale" | "failed";
  preview_url: string | null;
  is_stale: boolean;
  stale_reason: string | null;
  asset_slots: {
    slot_key: string;
    status: "empty" | "pending" | "filled";
    asset_version_id: string | null;
    preview_url: string | null;
  }[];
  etag: number;
}

export interface MockStyleContract {
  id: string;
  lesson_id: string;
  source_cover_result_id: string;
  summary: string;
  rules: Record<string, unknown>;
  cover_preview_url: string | null;
  created_at: string;
}

export interface MockVideoProject {
  id: string;
  lesson_id: string;
  status: "active" | "stale" | "archived";
  intro_snapshot: {
    option_key: string;
    title: string;
    category: "science" | "application" | "story";
    independent_concept: string;
    hook: string;
    viewer_value: string;
    course_anchor: string;
    classroom_first_question: string;
    handoff_moment: string;
    must_not_preteach: string[];
    suggested_medium: string | null;
    duration_seconds: number | null;
  };
  style_contract: {
    id: string;
    summary: string;
    rules: Record<string, unknown>;
    master_image_url: string | null;
  } | null;
  target_duration_seconds: number | null;
  created_at: string;
}

export interface MockShot {
  id: string;
  video_project_id: string;
  shot_key: string;
  position: number;
  status: "draft" | "ready" | "generating" | "review_required" | "adopted" | "failed" | "stale";
  shot: VideoShot;
  current_clip: {
    clip_id: string;
    result_id: string;
    preview_url: string | null;
    saved_at: string;
  } | null;
  active_job_id: string | null;
  failure_reason: string | null;
  etag: number;
}

export interface MockJob {
  id: string;
  kind: string;
  status:
    | "queued"
    | "running"
    | "waiting_provider"
    | "downloading"
    | "partially_completed"
    | "completed"
    | "failed"
    | "cancel_requested"
    | "cancelled";
  title: string;
  project_id: string | null;
  lesson_id: string | null;
  node_run_id: string | null;
  batch_id: string | null;
  phase_label: string | null;
  completed_items: number | null;
  total_items: number | null;
  failed_item_keys: string[];
  error: { code: string; message: string; retryable: boolean } | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
  /** 引擎推进计划（内部字段，不出现在响应中）。 */
  plan?: JobPlan;
}

export interface JobPlan {
  /** 每阶段 [状态, 持续 ms, 阶段文案]。 */
  phases: [MockJob["status"], number, string | null][];
  /** 完成时回调 key（engine 内部 dispatch）。 */
  onComplete: string;
  meta?: Record<string, unknown>;
}

export interface MockResult {
  id: string;
  batch_id: string | null;
  node_run_id: string | null;
  item_key: string;
  media_type: "image" | "video" | "ppt_page" | "document" | "audio";
  review_state: "pending" | "adopted" | "discarded";
  technical_check: "passed" | "failed" | "pending";
  technical_check_detail: string | null;
  preview_url: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  saved_binding_id: string | null;
  created_at: string;
}

export interface MockBatchItem {
  id: string;
  item_key: string;
  position: number;
  title: string;
  status: "draft" | "ready" | "queued" | "running" | "review_required" | "adopted" | "saved" | "failed";
  prompt: Record<string, unknown>;
  output_spec: Record<string, unknown>;
  reference_assets: { asset_version_id: string; role: string; preview_url?: string | null }[];
  target_slot_key: string | null;
  consistency_key: string | null;
  adopted_result_id: string | null;
  saved_binding_id: string | null;
}

export interface MockBatch {
  id: string;
  studio_type: "image" | "video" | "presentation";
  title: string;
  status: "draft" | "ready" | "running" | "partially_completed" | "completed" | "archived";
  creation_package_id: string | null;
  source_project_id: string | null;
  source_project_title: string | null;
  default_save_target: string | null;
  style_contract: Record<string, unknown> | null;
  items: MockBatchItem[];
  active_job_id: string | null;
  created_at: string;
  updated_at: string;
  etag: number;
}

export interface MockPackage {
  package_id: string;
  package_type: "image" | "video" | "presentation";
  status: "building" | "ready" | "invalid" | "expired";
  source: {
    project_id: string;
    lesson_unit_id: string | null;
    node_run_id: string;
    is_stale: boolean;
  };
  style_contract: Record<string, unknown> | null;
  items: {
    item_key: string;
    position: number;
    title: string;
    prompt: Record<string, unknown>;
    reference_assets?: { asset_version_id: string; role: string }[];
    output_spec: Record<string, unknown>;
    target_slot_key?: string | null;
    consistency_key?: string | null;
  }[];
  target_rules: Record<string, unknown>;
  created_at: string;
}

export interface MockAsset {
  id: string;
  project_id: string;
  kind: "image" | "video_clip" | "audio" | "subtitle" | "document" | "ppt_page";
  title: string;
  usage_label: string | null;
  source_label: string | null;
  lesson_id: string | null;
  lesson_title: string | null;
  slot_key: string | null;
  is_current: boolean;
  preview_url: string | null;
  version_no: number;
  created_at: string;
}

export interface MockProvider {
  id: string;
  display_name: string;
  capabilities: ("text" | "image" | "video" | "tts" | "layout")[];
  base_url: string | null;
  enabled: boolean;
  secret_status: "configured" | "missing" | "expiring";
  secret_tail: string | null;
  last_test: { status: "passed" | "failed"; tested_at: string; detail: string | null } | null;
  updated_at: string;
  etag: number;
}

export interface MockContentPackage {
  id: string;
  title: string;
  domain: "lesson_plan" | "intro_options" | "ppt" | "video" | "quality" | "style" | "prompt";
  status: "draft" | "checking" | "check_failed" | "dry_run" | "published";
  current_version_no: number;
  definition_key: string | null;
  definition: ContentDefinition | null;
  validation_issues: { key: string; severity: "error" | "warning" | "info"; message: string }[];
  versions: { version_no: number; published_at: string; note: string | null }[];
  test_cases: { key: string; title: string; status: "passed" | "failed" | "pending" }[];
  usage: { project_title: string; version_no: number }[];
  updated_at: string;
}

export interface MockAuditEvent {
  id: string;
  actor_name: string;
  action: string;
  resource_label: string;
  detail: string | null;
  occurred_at: string;
}

export interface MockStreamEvent {
  event_id: string;
  sequence_no: number;
  event_type: string;
  occurred_at: string;
  project_id: string | null;
  resource: { type: string; id: string };
  payload: Record<string, unknown>;
  request_id: string | null;
}

export interface MockAutomation {
  project_id: string;
  state: "idle" | "running" | "paused";
  paused_reason: "budget_confirmation_required" | "review_gate" | "hard_rule" | "failure" | null;
  paused_detail: string | null;
  pending_estimate: { minor_units: number; currency: string; summary: string | null } | null;
  spent_minor_units: number | null;
  budget_minor_units: number | null;
}

export interface MockDelivery {
  project_id: string;
  status: "not_ready" | "ready" | "packaging" | "packaged" | "stale";
  package: {
    version_no: number;
    created_at: string;
    files: {
      file_key: string;
      title: string;
      kind: "docx" | "pdf" | "pptx" | "mp4" | "srt" | "report" | "archive";
      size_bytes: number;
      asset_version_id: string | null;
    }[];
  } | null;
}

export interface MockIntroOptionState {
  lesson_id: string;
  set: IntroOptionSet;
  etag: number;
}

export interface MockDb {
  scenario: string;
  /** <1 加速任务推进（测试用 0 即时完成）。 */
  speedFactor: number;
  sessionUserId: string | null;
  users: MockUser[];
  projects: Map<string, MockProject>;
  materials: Map<string, MockMaterial>;
  divisions: Map<string, MockDivision>;
  lessons: Map<string, MockLesson>;
  nodeRuns: Map<string, MockNodeRun>;
  artifactVersions: Map<string, MockArtifactVersion>;
  prompts: Map<string, MockPrompt>;
  introOptionSets: Map<string, MockIntroOptionState>;
  introSelections: Map<string, MockIntroSelection>;
  pptPages: Map<string, MockPptPage>;
  styleContracts: Map<string, MockStyleContract>;
  videoProjects: Map<string, MockVideoProject>;
  shots: Map<string, MockShot>;
  jobs: Map<string, MockJob>;
  results: Map<string, MockResult>;
  batches: Map<string, MockBatch>;
  packages: Map<string, MockPackage>;
  assets: Map<string, MockAsset>;
  providers: Map<string, MockProvider>;
  contentPackages: Map<string, MockContentPackage>;
  auditEvents: MockAuditEvent[];
  automations: Map<string, MockAutomation>;
  deliveries: Map<string, MockDelivery>;
  events: MockStreamEvent[];
  eventSequence: number;
  idempotency: Map<string, { digest: string; body: unknown; status: number }>;
  idCounter: number;
}

function emptyDb(): MockDb {
  return {
    scenario: "default",
    speedFactor: 1,
    sessionUserId: null,
    users: [],
    projects: new Map(),
    materials: new Map(),
    divisions: new Map(),
    lessons: new Map(),
    nodeRuns: new Map(),
    artifactVersions: new Map(),
    prompts: new Map(),
    introOptionSets: new Map(),
    introSelections: new Map(),
    pptPages: new Map(),
    styleContracts: new Map(),
    videoProjects: new Map(),
    shots: new Map(),
    jobs: new Map(),
    results: new Map(),
    batches: new Map(),
    packages: new Map(),
    assets: new Map(),
    providers: new Map(),
    contentPackages: new Map(),
    auditEvents: [],
    automations: new Map(),
    deliveries: new Map(),
    events: [],
    eventSequence: 0,
    idempotency: new Map(),
    idCounter: 0,
  };
}

export const db: MockDb = emptyDb();

export function resetDb(): void {
  Object.assign(db, emptyDb());
}

export function nowIso(): string {
  return new Date().toISOString();
}

/** 运行期生成的 UUID（种子数据用 ids.ts 的稳定 ID）。 */
export function nextId(): string {
  db.idCounter += 1;
  const tail = String(db.idCounter).padStart(12, "0");
  return `00000000-9999-4000-8000-${tail}`;
}

export function nextRequestId(): string {
  db.idCounter += 1;
  return `req_mock_${db.idCounter}`;
}

/** 追加 SSE 事件（事件只触发前端 Query 刷新，不携带完整对象）。 */
export function emitEvent(input: {
  event_type: string;
  project_id?: string | null;
  resource: { type: string; id: string };
  payload?: Record<string, unknown>;
}): MockStreamEvent {
  db.eventSequence += 1;
  const event: MockStreamEvent = {
    event_id: nextId(),
    sequence_no: db.eventSequence,
    event_type: input.event_type,
    occurred_at: nowIso(),
    project_id: input.project_id ?? null,
    resource: input.resource,
    payload: input.payload ?? {},
    request_id: null,
  };
  db.events.push(event);
  if (db.events.length > 500) db.events.splice(0, db.events.length - 500);
  return event;
}

export function makeEtag(counter: number): string {
  return `W/"v${counter}"`;
}

export function touchLesson(lessonId: string): void {
  const lesson = db.lessons.get(lessonId);
  if (lesson) {
    lesson.updated_at = nowIso();
    lesson.etag += 1;
  }
}
