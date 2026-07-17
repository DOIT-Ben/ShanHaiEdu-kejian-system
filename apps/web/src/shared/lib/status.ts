/**
 * 五套独立状态模型的教师文案与视觉映射：
 * 节点（workflow-node-status.schema.json 15 态）、后台任务、候选审核、批准、保存。
 * 状态枚举与 contracts 保持一致；前端不得把中文文案反向作为状态判断依据。
 * 对未知状态显示「状态待升级」，不误判为成功（api-conventions.md）。
 */

export const NODE_STATUSES = [
  "disabled",
  "not_ready",
  "ready",
  "draft",
  "queued",
  "running",
  "review_required",
  "approved",
  "partially_completed",
  "failed",
  "paused",
  "cancel_requested",
  "cancelled",
  "stale",
  "skipped",
] as const;

export type NodeStatus = (typeof NODE_STATUSES)[number];

export type StatusTone = "neutral" | "brand" | "running" | "success" | "warning" | "danger";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
  hint?: string;
}

export const UNKNOWN_STATUS_META: StatusMeta = {
  label: "状态待升级",
  tone: "neutral",
  hint: "系统版本更新中，请刷新后查看。",
};

export const nodeStatusMeta: Record<NodeStatus, StatusMeta> = {
  disabled: { label: "未启用", tone: "neutral" },
  not_ready: { label: "等待前置步骤", tone: "neutral" },
  ready: { label: "可以开始", tone: "brand" },
  draft: { label: "草稿", tone: "neutral" },
  queued: { label: "排队中", tone: "running" },
  running: { label: "生成中", tone: "running" },
  review_required: { label: "等待你确认", tone: "warning" },
  approved: { label: "已完成", tone: "success" },
  partially_completed: { label: "部分完成", tone: "warning" },
  failed: { label: "生成失败", tone: "danger" },
  paused: { label: "已暂停", tone: "warning" },
  cancel_requested: { label: "正在停止", tone: "warning" },
  cancelled: { label: "已停止", tone: "neutral" },
  stale: { label: "内容已变化，建议更新", tone: "warning" },
  skipped: { label: "本次已跳过", tone: "neutral" },
};

export function getNodeStatusMeta(status: string): StatusMeta {
  return (nodeStatusMeta as Record<string, StatusMeta>)[status] ?? UNKNOWN_STATUS_META;
}

export const TASK_STATUSES = [
  "queued",
  "running",
  "waiting_provider",
  "downloading",
  "partially_completed",
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
  partially_completed: { label: "部分完成", tone: "warning" },
  completed: { label: "已完成", tone: "success" },
  failed: { label: "失败", tone: "danger" },
  cancel_requested: { label: "正在停止", tone: "warning" },
  cancelled: { label: "已停止", tone: "neutral" },
};

export function getTaskStatusMeta(status: string): StatusMeta {
  return (taskStatusMeta as Record<string, StatusMeta>)[status] ?? UNKNOWN_STATUS_META;
}

/** 候选结果审核状态（教师视角：待挑选 / 已采用 / 未采用）。 */
export const RESULT_REVIEW_STATES = ["pending", "adopted", "discarded"] as const;
export type ResultReviewState = (typeof RESULT_REVIEW_STATES)[number];

export const resultReviewMeta: Record<ResultReviewState, StatusMeta> = {
  pending: { label: "待挑选", tone: "neutral" },
  adopted: { label: "已采用", tone: "success" },
  discarded: { label: "未采用", tone: "neutral" },
};

/** 作品版本批准状态。 */
export const ARTIFACT_STATUSES = [
  "draft",
  "review_required",
  "approved",
  "rejected",
  "superseded",
] as const;

export type ArtifactStatus = (typeof ARTIFACT_STATUSES)[number];

export const artifactStatusMeta: Record<ArtifactStatus, StatusMeta> = {
  draft: { label: "草稿", tone: "neutral" },
  review_required: { label: "等待你确认", tone: "warning" },
  approved: { label: "已批准", tone: "success" },
  rejected: { label: "已驳回", tone: "danger" },
  superseded: { label: "已被新版本替代", tone: "neutral" },
};

export function getArtifactStatusMeta(status: string): StatusMeta {
  return (artifactStatusMeta as Record<string, StatusMeta>)[status] ?? UNKNOWN_STATUS_META;
}

/** 保存到项目的操作状态（与批准、候选状态独立）。 */
export type SaveOperationState = "idle" | "saving" | "saved" | "conflict" | "error";

export const saveOperationMeta: Record<SaveOperationState, StatusMeta> = {
  idle: { label: "未保存", tone: "neutral" },
  saving: { label: "保存中", tone: "running" },
  saved: { label: "已保存到项目", tone: "success" },
  conflict: { label: "目标位置已有内容", tone: "warning" },
  error: { label: "保存失败", tone: "danger" },
};

/** 分支聚合状态（项目总览用）。 */
export const BRANCH_STATES = [
  "disabled",
  "skipped",
  "not_ready",
  "in_progress",
  "review_required",
  "approved",
  "stale",
  "failed",
] as const;

export type BranchStateKey = (typeof BRANCH_STATES)[number];

export const branchStateMeta: Record<BranchStateKey, StatusMeta> = {
  disabled: { label: "未启用", tone: "neutral" },
  skipped: { label: "已跳过", tone: "neutral" },
  not_ready: { label: "未开始", tone: "neutral" },
  in_progress: { label: "制作中", tone: "running" },
  review_required: { label: "等待确认", tone: "warning" },
  approved: { label: "已完成", tone: "success" },
  stale: { label: "内容已变化", tone: "warning" },
  failed: { label: "有失败步骤", tone: "danger" },
};

export function getBranchStateMeta(state: string): StatusMeta {
  return (branchStateMeta as Record<string, StatusMeta>)[state] ?? UNKNOWN_STATUS_META;
}

export function isTaskActive(status: string): boolean {
  return (
    status === "queued" ||
    status === "running" ||
    status === "waiting_provider" ||
    status === "downloading" ||
    status === "cancel_requested"
  );
}

export function isNodeGenerating(status: string): boolean {
  return status === "queued" || status === "running";
}

export function isNodeActionable(status: string): boolean {
  return (
    status === "ready" ||
    status === "draft" ||
    status === "review_required" ||
    status === "partially_completed" ||
    status === "failed" ||
    status === "stale" ||
    status === "paused"
  );
}
