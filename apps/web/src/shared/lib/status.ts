/**
 * 节点状态、任务状态与产物状态的教师文案与视觉映射。
 * 状态枚举与 contracts/openapi.yaml 保持一致；
 * 前端不得把中文文案反向作为状态判断依据。
 */

export const NODE_STATUSES = [
  "locked",
  "ready",
  "queued",
  "running",
  "needs_review",
  "revision_required",
  "approved",
  "stale",
  "failed",
  "blocked",
  "cancelled",
  "skipped",
] as const;

export type NodeStatus = (typeof NODE_STATUSES)[number];

export type StatusTone = "neutral" | "brand" | "running" | "success" | "warning" | "danger";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
  hint?: string;
}

export const nodeStatusMeta: Record<NodeStatus, StatusMeta> = {
  locked: { label: "等待前置步骤", tone: "neutral" },
  ready: { label: "可以开始", tone: "brand" },
  queued: { label: "排队中", tone: "running" },
  running: { label: "生成中", tone: "running" },
  needs_review: { label: "待审核", tone: "warning" },
  revision_required: { label: "需要返修", tone: "warning" },
  approved: { label: "已批准", tone: "success" },
  stale: { label: "上游内容已变化", tone: "warning" },
  failed: { label: "生成失败", tone: "danger" },
  blocked: { label: "当前步骤被阻断", tone: "danger" },
  cancelled: { label: "已取消", tone: "neutral" },
  skipped: { label: "本项目已跳过", tone: "neutral" },
};

export const TASK_STATUSES = [
  "queued",
  "running",
  "waiting_provider",
  "downloading",
  "completed",
  "failed",
  "cancel_requested",
  "cancelled",
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

export const taskStatusMeta: Record<TaskStatus, StatusMeta> = {
  queued: { label: "排队中", tone: "running" },
  running: { label: "生成中", tone: "running" },
  waiting_provider: { label: "等待模型服务", tone: "running" },
  downloading: { label: "下载产物中", tone: "running" },
  completed: { label: "已完成", tone: "success" },
  failed: { label: "失败", tone: "danger" },
  cancel_requested: { label: "取消请求中", tone: "warning" },
  cancelled: { label: "已取消", tone: "neutral" },
};

export const ARTIFACT_STATUSES = [
  "draft",
  "needs_review",
  "approved",
  "stale",
  "superseded",
  "rejected",
] as const;

export type ArtifactStatus = (typeof ARTIFACT_STATUSES)[number];

export const artifactStatusMeta: Record<ArtifactStatus, StatusMeta> = {
  draft: { label: "草稿", tone: "neutral" },
  needs_review: { label: "待审核", tone: "warning" },
  approved: { label: "已批准", tone: "success" },
  stale: { label: "已失效", tone: "warning" },
  superseded: { label: "已被新版本替代", tone: "neutral" },
  rejected: { label: "已驳回", tone: "danger" },
};

export type AssetStatus = "draft" | "needs_review" | "approved" | "stale" | "rejected";

export const assetStatusMeta: Record<AssetStatus, StatusMeta> = {
  draft: { label: "草稿", tone: "neutral" },
  needs_review: { label: "待审核", tone: "warning" },
  approved: { label: "已批准", tone: "success" },
  stale: { label: "已失效", tone: "warning" },
  rejected: { label: "已驳回", tone: "danger" },
};

export function isTaskActive(status: TaskStatus): boolean {
  return (
    status === "queued" ||
    status === "running" ||
    status === "waiting_provider" ||
    status === "downloading" ||
    status === "cancel_requested"
  );
}

export function isNodeGenerating(status: NodeStatus): boolean {
  return status === "queued" || status === "running";
}
