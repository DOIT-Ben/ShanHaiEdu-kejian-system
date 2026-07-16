import type { ReactNode } from "react";
import { Badge } from "./badge";
import {
  nodeStatusMeta,
  taskStatusMeta,
  artifactStatusMeta,
  assetStatusMeta,
  type NodeStatus,
  type TaskStatus,
  type ArtifactStatus,
  type AssetStatus,
} from "@/shared/lib/status";
import {
  Lock,
  Play,
  Hourglass,
  Loader2,
  Eye,
  PencilLine,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Ban,
  MinusCircle,
  SkipForward,
  CloudDownload,
  FileClock,
  Layers,
} from "lucide-react";

const nodeStatusIcon: Record<NodeStatus, ReactNode> = {
  locked: <Lock className="size-3" aria-hidden />,
  ready: <Play className="size-3" aria-hidden />,
  queued: <Hourglass className="size-3" aria-hidden />,
  running: <Loader2 className="size-3 animate-spin" aria-hidden />,
  needs_review: <Eye className="size-3" aria-hidden />,
  revision_required: <PencilLine className="size-3" aria-hidden />,
  approved: <CheckCircle2 className="size-3" aria-hidden />,
  stale: <AlertTriangle className="size-3" aria-hidden />,
  failed: <XCircle className="size-3" aria-hidden />,
  blocked: <Ban className="size-3" aria-hidden />,
  cancelled: <MinusCircle className="size-3" aria-hidden />,
  skipped: <SkipForward className="size-3" aria-hidden />,
};

/** 状态不得只依赖颜色：所有状态徽章同时包含图标与文字。 */
export function NodeStatusBadge({ status, className }: { status: NodeStatus; className?: string }) {
  const meta = nodeStatusMeta[status];
  return (
    <Badge tone={meta.tone} icon={nodeStatusIcon[status]} className={className}>
      {meta.label}
    </Badge>
  );
}

const taskStatusIcon: Record<TaskStatus, ReactNode> = {
  queued: <Hourglass className="size-3" aria-hidden />,
  running: <Loader2 className="size-3 animate-spin" aria-hidden />,
  waiting_provider: <FileClock className="size-3" aria-hidden />,
  downloading: <CloudDownload className="size-3" aria-hidden />,
  completed: <CheckCircle2 className="size-3" aria-hidden />,
  failed: <XCircle className="size-3" aria-hidden />,
  cancel_requested: <MinusCircle className="size-3" aria-hidden />,
  cancelled: <MinusCircle className="size-3" aria-hidden />,
};

export function TaskStatusBadge({ status, className }: { status: TaskStatus; className?: string }) {
  const meta = taskStatusMeta[status];
  return (
    <Badge tone={meta.tone} icon={taskStatusIcon[status]} className={className}>
      {meta.label}
    </Badge>
  );
}

export function ArtifactStatusBadge({
  status,
  className,
}: {
  status: ArtifactStatus;
  className?: string;
}) {
  const meta = artifactStatusMeta[status];
  return (
    <Badge tone={meta.tone} icon={<Layers className="size-3" aria-hidden />} className={className}>
      {meta.label}
    </Badge>
  );
}

export function AssetStatusBadge({ status, className }: { status: AssetStatus; className?: string }) {
  const meta = assetStatusMeta[status];
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}
