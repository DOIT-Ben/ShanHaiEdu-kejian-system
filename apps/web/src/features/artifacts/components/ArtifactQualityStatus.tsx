import type { AcceptedNodeRunDto } from "@/features/artifacts/api/artifactsApi";
import type { NodeRunDto } from "@/features/workflow/api/workflowApi";

type ArtifactQualityStatusProps = {
  accepted?: AcceptedNodeRunDto;
  nodeRuns?: readonly NodeRunDto[];
  subject: string;
};

const incompleteStatuses = new Set<NodeRunDto["status"]>([
  "cancel_requested",
  "cancelled",
  "disabled",
  "skipped",
  "stale",
]);

function qualityStatusMessage(subject: string, status: NodeRunDto["status"]) {
  if (status === "approved") return `${subject}质量校验已通过，可以批准当前版本。`;
  if (status === "failed") return `${subject}质量校验未通过，请修订当前版本后重新校验。`;
  if (incompleteStatuses.has(status)) return `${subject}质量校验未完成，请重新运行。`;
  if (
    status === "queued" ||
    status === "running" ||
    status === "review_required" ||
    status === "partially_completed"
  ) {
    return `${subject}质量校验正在处理。`;
  }
  return `${subject}质量校验已提交，正在等待 Worker。`;
}

export function ArtifactQualityStatus({
  accepted,
  nodeRuns = [],
  subject,
}: ArtifactQualityStatusProps) {
  if (!accepted) return null;
  const status =
    nodeRuns.find((nodeRun) => nodeRun.id === accepted.node_run_id)?.status ?? accepted.status;
  const failed = status === "failed" || incompleteStatuses.has(status);
  const className =
    status === "approved"
      ? "text-sm text-[var(--sh-success)]"
      : failed
        ? "text-sm text-[var(--sh-danger)]"
        : "text-sm text-[var(--sh-ink-muted)]";

  return (
    <p className={className} role={failed ? "alert" : "status"}>
      {qualityStatusMessage(subject, status)}
    </p>
  );
}
