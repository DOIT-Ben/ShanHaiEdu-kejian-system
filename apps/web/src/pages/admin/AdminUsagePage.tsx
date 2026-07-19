import { AlertTriangle, CircleDollarSign, Clock3, ListTodo, RefreshCw } from "lucide-react";
import { useState } from "react";
import {
  createMockTask,
  getMockDraft,
  saveMockDraft,
  updateMockTask,
  useMockRuntime,
} from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

const USAGE_DRAFT_KEY = "admin.usage-view";

const failedJobs = [
  {
    title: "PPT 图片 · 百格光窗",
    reason: "画面文字检查未通过",
    capability: "教学图片",
    time: "11:42",
  },
  {
    title: "导入视频 · 镜头 3",
    reason: "视频首尾状态不连续",
    capability: "课堂视频",
    time: "10:18",
  },
  { title: "课堂旁白 · 场次 2", reason: "语音服务响应超时", capability: "语音合成", time: "09:56" },
];

export function AdminUsagePage() {
  const tasks = useMockRuntime((state) => state.tasks);
  const [ruleOpen, setRuleOpen] = useState(false);
  const [refreshedAt, setRefreshedAt] = useState(
    () => getMockDraft<{ refreshedAt: string }>(USAGE_DRAFT_KEY)?.value.refreshedAt ?? "",
  );
  const retryJob = (job: (typeof failedJobs)[number]) => {
    const current = tasks.find((task) => task.title === job.title);
    if (current) {
      updateMockTask(current.id, {
        detail: `${job.reason}；已提交重新处理`,
        stage: "等待重试",
        status: "queued",
        progress: 0,
        retry_count: current.retry_count + 1,
      });
      return;
    }
    createMockTask({
      title: job.title,
      detail: `${job.reason}；已提交重新处理`,
      stage: "等待重试",
      status: "queued",
      progress: 0,
      retry_count: 1,
    });
  };
  const refresh = () => {
    const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    saveMockDraft(USAGE_DRAFT_KEY, { refreshedAt: time });
    setRefreshedAt(time);
  };
  return (
    <div className="p-5 md:p-6">
      <FocusPageHeader
        description="聚焦任务积压、失败、异常服务和费用异常，提供可直接处理的动作。"
        title="运行与费用"
      />
      <div className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          [
            ListTodo,
            "当前积压",
            String(tasks.filter((task) => task.status === "queued").length),
            "等待安排的任务",
          ],
          [AlertTriangle, "近 24 小时失败率", "3.8%", "视频服务高于平时"],
          [CircleDollarSign, "今日费用", "¥286.40", "预算使用 72%"],
          [Clock3, "最长等待", "18 分钟", "课堂视频队列"],
        ].map(([Icon, title, value, detail]) => {
          const Comp = Icon as typeof ListTodo;
          return (
            <article
              className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5"
              key={String(title)}
            >
              <Comp aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
              <p className="mt-4 text-sm text-[var(--sh-ink-muted)]">{String(title)}</p>
              <p className="mt-1 text-2xl font-bold text-[var(--sh-ink-strong)]">{String(value)}</p>
              <p className="mt-2 text-xs text-[var(--sh-ink-faint)]">{String(detail)}</p>
            </article>
          );
        })}
      </div>
      <section className="mt-6 rounded-[var(--sh-radius-md)] border border-[var(--sh-warning)]/30 bg-[var(--sh-warning-soft)] p-5">
        <div className="flex flex-wrap items-start gap-4">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-5 text-[var(--sh-warning)]" />
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">课堂视频服务响应变慢</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              最近 30 分钟平均等待 14 分钟，系统已将新任务限制为 2 个并发。已有任务不会取消。
            </p>
          </div>
          <Button onClick={() => setRuleOpen((open) => !open)} size="sm" variant="secondary">
            查看服务规则
          </Button>
        </div>
        {ruleOpen ? (
          <div className="mt-4 rounded-[var(--sh-radius-sm)] border border-[var(--sh-warning)]/30 bg-[var(--sh-surface-elevated)] p-4 text-sm">
            <h3 className="font-semibold text-[var(--sh-ink-strong)]">课堂视频服务规则</h3>
            <p className="mt-2 text-[var(--sh-ink-muted)]">
              新任务并发上限为 2，单任务最长等待 20 分钟；超时任务进入人工确认，不自动取消已有任务。
            </p>
          </div>
        ) : null}
      </section>
      <section className="mt-7">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-[var(--sh-ink-strong)]">需要处理的失败任务</h2>
          <Button onClick={refresh} size="sm" variant="quiet">
            <RefreshCw aria-hidden="true" />
            刷新
          </Button>
        </div>
        <div className="divide-y divide-[var(--sh-line-subtle)] rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-5">
          {failedJobs.map((job) => {
            const runtimeTask = tasks.find((task) => task.title === job.title);
            const canRetry =
              !runtimeTask || runtimeTask.status === "failed" || runtimeTask.status === "cancelled";
            const actionLabel =
              !runtimeTask || runtimeTask.status === "failed"
                ? "查看并重试"
                : runtimeTask.status === "queued"
                  ? "重试已提交"
                  : runtimeTask.status === "running"
                    ? "重试进行中"
                    : runtimeTask.status === "approved"
                      ? "重试已完成"
                      : runtimeTask.status === "cancelled"
                        ? "重新提交重试"
                        : "查看任务状态";
            return (
              <div className="flex flex-wrap items-center gap-4 py-5" key={job.title}>
                <StatusBadge status={runtimeTask?.status ?? "failed"} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">{job.title}</p>
                  <p className="mt-1 text-xs text-[var(--sh-ink-muted)]">
                    {runtimeTask?.detail ?? `${job.reason} · ${job.capability}`}
                  </p>
                </div>
                <span className="text-xs text-[var(--sh-ink-faint)]">{job.time}</span>
                <Button
                  disabled={!canRetry}
                  onClick={() => retryJob(job)}
                  size="sm"
                  variant="secondary"
                >
                  {actionLabel}
                </Button>
              </div>
            );
          })}
        </div>
        {refreshedAt ? (
          <p aria-live="polite" className="mt-3 text-sm text-[var(--sh-ink-muted)]">
            任务列表已刷新 · {refreshedAt}
          </p>
        ) : null}
      </section>
    </div>
  );
}
