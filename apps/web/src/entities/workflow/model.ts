export const workflowStatuses = [
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

export type ContractWorkflowStatus = (typeof workflowStatuses)[number];
export type WorkflowStatus = ContractWorkflowStatus | "unknown";

export function parseWorkflowStatus(status: string): WorkflowStatus {
  return workflowStatuses.includes(status as ContractWorkflowStatus)
    ? (status as ContractWorkflowStatus)
    : "unknown";
}
