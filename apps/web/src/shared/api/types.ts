import type { components } from "./generated";

/** 由 OpenAPI 生成类型导出的常用领域别名；不得手写第二套 DTO。 */
export type User = components["schemas"]["User"];
export type Project = components["schemas"]["Project"];
export type AutomationMode = components["schemas"]["AutomationMode"];
export type AutomationState = components["schemas"]["AutomationState"];
export type Material = components["schemas"]["Material"];
export type Lesson = components["schemas"]["Lesson"];
export type BranchState = components["schemas"]["BranchState"];
export type NodeRun = components["schemas"]["NodeRun"];
export type NodeStatus = components["schemas"]["NodeStatus"];
export type ArtifactVersion = components["schemas"]["ArtifactVersion"];
export type ValidationIssue = components["schemas"]["ValidationIssue"];
export type GenerationJob = components["schemas"]["GenerationJob"];
export type GenerationResult = components["schemas"]["GenerationResult"];
export type CreationBatch = components["schemas"]["CreationBatch"];
export type CreationBatchItem = components["schemas"]["CreationBatchItem"];
export type IntroSelection = components["schemas"]["IntroSelection"];
export type PptRuntimePage = components["schemas"]["PptRuntimePage"];
export type PptStyleContract = components["schemas"]["PptStyleContract"];
export type VideoProject = components["schemas"]["VideoProject"];
export type VideoRuntimeShot = components["schemas"]["VideoRuntimeShot"];
export type AssetVersion = components["schemas"]["AssetVersion"];
export type Provider = components["schemas"]["Provider"];
export type ContentPackage = components["schemas"]["ContentPackage"];
export type AdminWorkflow = components["schemas"]["AdminWorkflow"];

export type HomeOverview = components["schemas"]["HomeOverviewEnvelope"]["data"];
export type PendingAction = HomeOverview["pending_actions"][number];
export type ContinueItem = HomeOverview["continue_items"][number];
export type LessonDivision = components["schemas"]["LessonDivisionEnvelope"]["data"];
export type LessonDivisionEntry = LessonDivision["entries"][number];
export type PromptPreview = components["schemas"]["PromptPreviewEnvelope"]["data"];
export type NodeRunDetail = components["schemas"]["NodeRunDetailEnvelope"]["data"];
export type Delivery = components["schemas"]["DeliveryEnvelope"]["data"];
export type PptPageDetail = components["schemas"]["PptPageEnvelope"]["data"];
export type AcceptedJob = components["schemas"]["AcceptedJobEnvelope"]["data"];
export type SaveOperation = components["schemas"]["SaveOperationEnvelope"]["data"];
export type UsageOverview = components["schemas"]["UsageOverviewEnvelope"]["data"];
export type ModelServiceOverview = components["schemas"]["ModelServiceOverviewEnvelope"]["data"];
export type ContentPackageDetail = components["schemas"]["ContentPackageEnvelope"]["data"];
export type AdminWorkflowDetail = components["schemas"]["AdminWorkflowEnvelope"]["data"];
export type AuditEvent =
  components["schemas"]["AuditEventListEnvelope"]["data"]["items"][number];
export type AdminUser =
  components["schemas"]["AdminUserListEnvelope"]["data"]["items"][number];
export type ModelCatalogEntry =
  components["schemas"]["ModelCatalogEnvelope"]["data"]["items"][number];
export type ModelRun =
  components["schemas"]["ModelRunListEnvelope"]["data"]["items"][number];
export type AssetSummaryCard = NonNullable<
  components["schemas"]["AssetListEnvelope"]["data"]["summary_cards"]
>[number];
