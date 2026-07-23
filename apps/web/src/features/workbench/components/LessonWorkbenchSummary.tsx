import { Link } from "react-router-dom";
import { WorkbenchStatusBoard, type WorkbenchStatusItem } from "./WorkbenchStatusBoard";

export type LessonBranchSummary = {
  enabled: boolean;
  key: string;
  label: string;
  to: string;
};

type LessonWorkbenchSummaryProps = {
  branches: readonly LessonBranchSummary[];
  currentBranchKey: string;
  durationLabel?: string;
  lessonTitle: string;
  objective: string;
  progressErrorMessage?: string;
  progressState?: "error" | "loading" | "ready";
  statuses: readonly WorkbenchStatusItem[];
};

export function LessonWorkbenchSummary({
  branches,
  currentBranchKey,
  durationLabel,
  lessonTitle,
  objective,
  progressErrorMessage,
  progressState,
  statuses,
}: LessonWorkbenchSummaryProps) {
  const currentBranch = branches.find((branch) => branch.key === currentBranchKey);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section aria-labelledby="workbench-summary-title" className="min-w-0">
        <div className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)] md:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs font-medium text-[var(--sh-ink-faint)]">当前课时</p>
              <h2
                className="mt-2 text-xl font-semibold text-[var(--sh-ink-strong)]"
                id="workbench-summary-title"
              >
                {lessonTitle}
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--sh-ink-muted)]">
                {objective}
              </p>
            </div>
            {durationLabel ? (
              <span className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-3 py-1.5 text-xs text-[var(--sh-ink-muted)]">
                {durationLabel}
              </span>
            ) : null}
          </div>
          <div className="mt-6 border-t border-[var(--sh-line-subtle)] pt-5">
            <h3 className="text-sm font-semibold text-[var(--sh-ink-strong)]">制作进度</h3>
            <WorkbenchStatusBoard
              errorMessage={progressErrorMessage}
              items={statuses}
              state={progressState}
            />
          </div>
        </div>
      </section>

      <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
        <h2 className="font-semibold text-[var(--sh-ink-strong)]">课时分支</h2>
        <nav aria-label="课时分支" className="mt-4 grid gap-1.5">
          {branches.map((branch) => (
            <Link
              aria-current={branch.key === currentBranchKey ? "page" : undefined}
              className={`flex items-center justify-between rounded-[var(--sh-radius-sm)] px-3 py-2.5 text-sm transition-colors ${branch.key === currentBranchKey ? "bg-[var(--sh-brand-50)] font-medium text-[var(--sh-brand-700)]" : "text-[var(--sh-ink-muted)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)]"}`}
              key={branch.key}
              to={branch.to}
            >
              <span>{branch.label}</span>
              <span className="text-xs">{branch.enabled ? "可用" : "未启用"}</span>
            </Link>
          ))}
        </nav>
        {currentBranch && !currentBranch.enabled ? (
          <p className="mt-4 text-xs leading-5 text-[var(--sh-ink-muted)]">
            该分支当前未启用，不会创建新的制作任务。
          </p>
        ) : null}
      </aside>
    </div>
  );
}
