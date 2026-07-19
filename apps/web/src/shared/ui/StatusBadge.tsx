import type { WorkflowStatus } from "@/entities/workflow/model";
import { cn } from "@/shared/lib/cn";

const statusMeta: Record<WorkflowStatus, { label: string; className: string }> = {
  disabled: {
    label: "未启用",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
  },
  not_ready: {
    label: "等待前置内容",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
  },
  ready: { label: "可以开始", className: "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]" },
  draft: { label: "草稿", className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-default)]" },
  queued: { label: "等待处理", className: "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]" },
  running: { label: "制作中", className: "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]" },
  review_required: {
    label: "等待你确认",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-accent-caramel-strong)]",
  },
  approved: {
    label: "已完成",
    className: "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]",
  },
  partially_completed: {
    label: "部分完成",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-accent-caramel-strong)]",
  },
  failed: {
    label: "需要处理",
    className: "bg-[var(--sh-danger-soft)] text-[var(--sh-danger-strong)]",
  },
  paused: {
    label: "已暂停",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-accent-caramel-strong)]",
  },
  cancel_requested: {
    label: "正在取消",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-default)]",
  },
  cancelled: {
    label: "已取消",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
  },
  stale: {
    label: "内容已变化，建议更新",
    className: "bg-[var(--sh-warning-soft)] text-[var(--sh-accent-caramel-strong)]",
  },
  skipped: {
    label: "本次已跳过",
    className: "bg-[var(--sh-surface-soft)] text-[var(--sh-ink-muted)]",
  },
  unknown: {
    label: "状态待升级",
    className: "bg-[var(--sh-danger-soft)] text-[var(--sh-danger-strong)]",
  },
};

export function StatusBadge({ status }: { status: WorkflowStatus }) {
  const meta = Object.hasOwn(statusMeta, status) ? statusMeta[status] : statusMeta.unknown;
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center rounded-full border border-transparent px-2.5 py-0.5 text-xs font-medium",
        meta.className,
      )}
    >
      {meta.label}
    </span>
  );
}
