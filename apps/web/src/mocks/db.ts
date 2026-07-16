import type {
  AdminUser,
  ArtifactVersion,
  Asset,
  AssetVersion,
  AuditEntry,
  BudgetConfig,
  Delivery,
  Lesson,
  ModelDefinition,
  ModelRun,
  NodeSummary,
  Organization,
  Project,
  PromptVersion,
  Provider,
  RoutePolicy,
  Task,
  TemplateDetail,
  UsageReference,
  User,
  ValidationResult,
  WorkflowVersion,
  WorkflowVersionDetail,
} from "@/shared/api/types";
import type { StreamEvent } from "@/shared/api/eventStream";

/** 场景行为开关（由 handlers 与 engine 读取）。 */
export interface ScenarioFlags {
  loginAlwaysFail?: boolean;
  sessionExpiredOnFirstMe?: boolean;
  emptyProjects?: boolean;
  slowProjectList?: boolean;
  textbookUploadRunning?: boolean;
  evidencePartial?: boolean;
  parseFails?: boolean;
  divisionConflictOnSave?: boolean;
  lessonPlanStreaming?: boolean;
  anchorFailed?: boolean;
  imagePartialFail?: boolean;
  clipPartialFail?: boolean;
  budgetAuthRequired?: boolean;
  paidFallbackConfirm?: boolean;
  providerDegraded?: boolean;
  /** SSE：N 毫秒后服务端主动断流（重连演示）。 */
  sseDropAfterMs?: number;
  /** SSE：始终 500（轮询降级演示）。 */
  sseAlwaysFail?: boolean;
  staleDownstream?: boolean;
  deliveryBlocked?: boolean;
  deliveryCompleted?: boolean;
  pptExportRunning?: boolean;
  videoFinalProcessing?: boolean;
  clipApprovalReady?: boolean;
}

export interface NodeState {
  summary: NodeSummary;
  description: string;
  inputSchema: Record<string, unknown>;
  inputValues: Record<string, unknown>;
  inputRowVersion: number;
  draftContent: Record<string, unknown> | null;
  draftRowVersion: number;
  selectedAssetIds: string[];
  promptVersions: PromptVersion[];
  artifactVersions: ArtifactVersion[];
  validationResults: ValidationResult[];
  activeTaskId: string | null;
}

export interface AssetRecord {
  asset: Asset;
  versions: AssetVersion[];
  usage: UsageReference[];
  projectId: string;
}

export interface LessonState {
  lesson: Lesson;
  nodes: Map<string, NodeState>;
  currentNodeKey: string;
}

export interface ProjectState {
  project: Project;
  evidence: ArtifactVersion | null;
  division: ArtifactVersion | null;
  divisionVersions: ArtifactVersion[];
  lessons: LessonState[];
  delivery: Delivery;
}

export interface MockAccount {
  user: User;
  password: string;
}

export interface MockDb {
  scenario: string;
  flags: ScenarioFlags;
  /** 任务时长倍率（测试环境调小加速）。 */
  speedFactor: number;
  seq: number;
  session: { user: User; csrfToken: string } | null;
  firstMeServed: boolean;
  divisionConflictServed: boolean;
  accounts: MockAccount[];
  projects: Map<string, ProjectState>;
  tasks: Map<string, Task>;
  taskCallbacks: Map<string, () => void>;
  idempotency: Map<string, string>;
  assets: Map<string, AssetRecord>;
  fileNames: Map<string, string>;
  events: StreamEvent[];
  users: AdminUser[];
  organizations: Organization[];
  providers: Provider[];
  models: ModelDefinition[];
  routes: RoutePolicy[];
  budgets: BudgetConfig;
  modelRuns: ModelRun[];
  templates: Map<string, TemplateDetail>;
  workflows: WorkflowVersion[];
  workflowDetails: Map<string, WorkflowVersionDetail>;
  audit: AuditEntry[];
}

let activeDb: MockDb | null = null;

export function setActiveDb(db: MockDb): void {
  activeDb = db;
}

export function getDb(): MockDb {
  if (!activeDb) {
    throw new Error("Mock 数据库尚未初始化（先调用 seedDb）");
  }
  return activeDb;
}

export function nextId(db: MockDb, prefix: string): string {
  db.seq += 1;
  return `${prefix}_${String(db.seq).padStart(5, "0")}`;
}

export function nowIso(offsetMs = 0): string {
  return new Date(Date.now() + offsetMs).toISOString();
}

export function minutesAgo(minutes: number): string {
  return nowIso(-minutes * 60_000);
}

export function traceId(db: MockDb): string {
  return nextId(db, "trace");
}
