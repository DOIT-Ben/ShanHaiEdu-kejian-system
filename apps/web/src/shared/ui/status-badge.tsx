import type { ReactNode } from "react";
import { Badge } from "./badge";
import {
  getArtifactStatusMeta,
  getNodeStatusMeta,
  getTaskStatusMeta,
  resultReviewMeta,
  saveOperationMeta,
  type ResultReviewState,
  type SaveOperationState,
} from "@/shared/lib/status";
import {
  Lock,
  Play,
  Hourglass,
  Loader2,
  Eye,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  PauseCircle,
  MinusCircle,
  SkipForward,
  CloudDownload,
  FileClock,
  CircleDashed,
  PencilLine,
  Layers,
  Save,
} from "lucide-react";

const nodeStatusIcon: Record<string, ReactNode> = {
  disabled: <MinusCircle className="size-3" aria-hidden />,
  not_ready: <Lock className="size-3" aria-hidden />,
  ready: <Play className="size-3" aria-hidden />,
  draft: <PencilLine className="size-3" aria-hidden />,
  queued: <Hourglass className="size-3" aria-hidden />,
  running: <Loader2 className="size-3 animate-spin" aria-hidden />,
  review_required: <Eye className="size-3" aria-hidden />,
  approved: <CheckCircle2 className="size-3" aria-hidden />,
  partially_completed: <AlertTriangle className="size-3" aria-hidden />,
  failed: <XCircle className="size-3" aria-hidden />,
  paused: <PauseCircle className="size-3" aria-hidden />,
  cancel_requested: <MinusCircle className="size-3" aria-hidden />,
  cancelled: <MinusCircle className="size-3" aria-hidden />,
  stale: <AlertTriangle className="size-3" aria-hidden />,
  skipped: <SkipForward className="size-3" aria-hidden />,
};

/** 状态不得只依赖颜色：所有状态徽章同时包含图标与文字。 */
export function NodeStatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = getNodeStatusMeta(status);
  return (
    <Badge
      tone={meta.tone}
      icon={nodeStatusIcon[status] ?? <CircleDashed className="size-3" aria-hidden />}
      className={className}
    >
      {meta.label}
    </Badge>
  );
}

const taskStatusIcon: Record<string, ReactNode> = {
  queued: <Hourglass className="size-3" aria-hidden />,
  running: <Loader2 className="size-3 animate-spin" aria-hidden />,
  waiting_provider: <FileClock className="size-3" aria-hidden />,
  downloading: <CloudDownload className="size-3" aria-hidden />,
  partially_completed: <AlertTriangle className="size-3" aria-hidden />,
  completed: <CheckCircle2 className="size-3" aria-hidden />,
  failed: <XCircle className="size-3" aria-hidden />,
  cancel_requested: <MinusCircle className="size-3" aria-hidden />,
  cancelled: <MinusCircle className="size-3" aria-hidden />,
};

export function TaskStatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = getTaskStatusMeta(status);
  return (
    <Badge
      tone={meta.tone}
      icon={taskStatusIcon[status] ?? <CircleDashed className="size-3" aria-hidden />}
      className={className}
    >
      {meta.label}
    </Badge>
  );
}

export function ArtifactStatusBadge({ status, className }: { status: string; className?: string }) {
  const meta = getArtifactStatusMeta(status);
  return (
    <Badge tone={meta.tone} icon={<Layers className="size-3" aria-hidden />} className={className}>
      {meta.label}
    </Badge>
  );
}

export function ResultReviewBadge({
  state,
  className,
}: {
  state: ResultReviewState;
  className?: string;
}) {
  const meta = resultReviewMeta[state];
  return (
    <Badge tone={meta.tone} className={className}>
      {meta.label}
    </Badge>
  );
}

export function SaveOperationBadge({
  state,
  className,
}: {
  state: SaveOperationState;
  className?: string;
}) {
  const meta = saveOperationMeta[state];
  return (
    <Badge tone={meta.tone} icon={<Save className="size-3" aria-hidden />} className={className}>
      {meta.label}
    </Badge>
  );
}
