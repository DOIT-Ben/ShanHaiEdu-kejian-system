import {
  Archive,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleDot,
  CircleX,
  Clock3,
  LoaderCircle,
  PauseCircle,
} from "lucide-react";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { cn } from "@/shared/lib/cn";

const statusMeta: Record<
  WorkflowStatus,
  { className: string; icon: typeof CircleDot; label: string }
> = {
  disabled: {
    label: "未启用",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
    icon: CircleDashed,
  },
  not_ready: {
    label: "等待前置内容",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
    icon: Clock3,
  },
  ready: {
    label: "可以开始",
    className: "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]",
    icon: CircleDot,
  },
  draft: {
    label: "草稿",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-default)]",
    icon: CircleDashed,
  },
  queued: {
    label: "等待处理",
    className: "bg-[var(--sh-info-soft)] text-[var(--sh-info-strong)]",
    icon: Clock3,
  },
  running: {
    label: "制作中",
    className: "bg-[var(--sh-info-soft)] text-[var(--sh-info-strong)]",
    icon: LoaderCircle,
  },
  review_required: {
    label: "等待你确认",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]",
    icon: CircleAlert,
  },
  approved: {
    label: "已完成",
    className: "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]",
    icon: CircleCheck,
  },
  partially_completed: {
    label: "部分完成",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]",
    icon: CircleAlert,
  },
  failed: {
    label: "需要处理",
    className: "bg-[var(--sh-danger-soft)] text-[var(--sh-danger-strong)]",
    icon: CircleX,
  },
  paused: {
    label: "已暂停",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]",
    icon: PauseCircle,
  },
  cancel_requested: {
    label: "正在取消",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-default)]",
    icon: LoaderCircle,
  },
  cancelled: {
    label: "已取消",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
    icon: CircleX,
  },
  stale: {
    label: "内容已变化，建议更新",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]",
    icon: CircleAlert,
  },
  skipped: {
    label: "本次已跳过",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
    icon: Archive,
  },
  unknown: {
    label: "状态待升级",
    className: "bg-[var(--sh-danger-soft)] text-[var(--sh-danger-strong)]",
    icon: CircleAlert,
  },
};

export function StatusBadge({ status }: { status: WorkflowStatus }) {
  const meta = Object.hasOwn(statusMeta, status) ? statusMeta[status] : statusMeta.unknown;
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-[var(--sh-radius-sm)] border border-transparent px-2.5 py-0.5 text-xs font-medium",
        meta.className,
      )}
    >
      <Icon
        aria-hidden="true"
        className={cn(
          "size-3.5 shrink-0",
          meta.icon === LoaderCircle && "animate-spin motion-reduce:animate-none",
        )}
      />
      {meta.label}
    </span>
  );
}
