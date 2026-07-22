import { CircleAlert } from "lucide-react";
import { parseWorkflowStatus, type WorkflowStatus } from "@/entities/workflow/model";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export type WorkbenchStatusItem = {
  detail?: string;
  id: string;
  status: string;
  title: string;
};

type WorkbenchStatusBoardProps = {
  errorMessage?: string;
  items: WorkbenchStatusItem[];
  state?: "error" | "loading" | "ready";
};

const labels: Record<string, string> = {
  cancelled: "已取消",
  failed: "处理失败",
  not_started: "未开始",
  paused: "已暂停",
  queued: "等待处理",
  ready: "待开始",
  running: "正在处理",
  stale: "内容已变化",
  succeeded: "已完成",
};

function badgeStatus(status: string): WorkflowStatus {
  return status === "succeeded" ? "approved" : parseWorkflowStatus(status);
}

export function WorkbenchStatusBoard({
  errorMessage = "服务端状态暂时无法读取，请稍后重试。",
  items,
  state = "ready",
}: WorkbenchStatusBoardProps) {
  if (state === "loading") {
    return (
      <div aria-label="正在读取节点状态" className="mt-3 grid gap-2" role="status">
        <div className="h-11 animate-pulse rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
        <div className="h-11 animate-pulse rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
      </div>
    );
  }
  if (state === "error") {
    return (
      <p
        aria-label="节点状态读取失败"
        className="mt-3 flex items-center gap-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] px-3 py-3 text-sm text-[var(--sh-danger-strong)]"
        role="alert"
      >
        <CircleAlert aria-hidden="true" className="size-4 shrink-0" />
        {errorMessage}
      </p>
    );
  }
  if (items.length === 0) {
    return (
      <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 py-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
        这一步还没有服务端节点记录。先完成上游确认，系统才会创建可执行的制作任务。
      </p>
    );
  }
  return (
    <ul className="mt-3 grid gap-2" aria-label="当前节点状态">
      {items.map((item) => (
        <li
          className="flex items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] border border-[var(--sh-line-subtle)] px-3 py-3"
          key={item.id}
        >
          <span className="min-w-0">
            <span className="block truncate text-sm text-[var(--sh-ink-strong)]">{item.title}</span>
            {item.detail ? (
              <span className="mt-1 block truncate text-xs text-[var(--sh-ink-muted)]">
                {item.detail}
              </span>
            ) : null}
          </span>
          <StatusBadge
            label={labels[item.status] ?? item.status}
            status={badgeStatus(item.status)}
          />
        </li>
      ))}
    </ul>
  );
}
