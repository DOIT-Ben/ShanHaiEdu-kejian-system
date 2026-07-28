import { BookOpenText, Clapperboard, Presentation, Sparkles } from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import { Link } from "react-router-dom";
import { cn } from "@/shared/lib/cn";

export type LessonBranchSummary = {
  available: boolean;
  enabled: boolean;
  key: string;
  label: string;
  to: string;
};

type LessonWorkbenchSummaryProps = {
  branches: readonly LessonBranchSummary[];
  currentBranchKey: string;
  durationLabel?: string;
  objective: string;
};

const stepIcons: Record<string, ComponentType<SVGProps<SVGSVGElement>>> = {
  intro_options: Sparkles,
  lesson_plan: BookOpenText,
  ppt: Presentation,
  video: Clapperboard,
};

function stepStatus(branch: LessonBranchSummary, current: boolean) {
  if (!branch.available) return "尚未开放";
  if (!branch.enabled) return "未启用";
  return current ? "当前步骤" : "可进入";
}

function stepClass(current: boolean, interactive: boolean) {
  return cn(
    "flex min-h-14 min-w-0 items-center gap-3 border-l-2 px-3 py-2.5 text-left transition-colors duration-[var(--sh-duration-fast)] motion-reduce:transition-none",
    current
      ? "border-l-[var(--sh-action-primary)] bg-[var(--sh-brand-50)] text-[var(--sh-ink-strong)]"
      : "border-l-transparent text-[var(--sh-ink-muted)]",
    interactive &&
      !current &&
      "hover:border-l-[var(--sh-brand-300)] hover:bg-[var(--sh-surface-soft)] hover:text-[var(--sh-ink-strong)] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)]",
    !interactive && "cursor-not-allowed opacity-70",
  );
}

export function LessonWorkbenchSummary({
  branches,
  currentBranchKey,
  durationLabel,
  objective,
}: LessonWorkbenchSummaryProps) {
  return (
    <section
      aria-label="课时制作概览"
      className="border-y border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)]"
    >
      <div className="grid gap-3 px-1 py-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <p className="min-w-0 text-sm leading-6 text-[var(--sh-ink-muted)]">{objective}</p>
        {durationLabel ? (
          <span className="w-fit rounded-[var(--sh-radius-control)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] px-2.5 py-1 text-xs font-medium text-[var(--sh-ink-muted)]">
            {durationLabel}
          </span>
        ) : null}
      </div>
      <nav
        aria-label="课时制作步骤"
        className="grid grid-cols-1 border-t border-[var(--sh-line-subtle)] min-[520px]:grid-cols-2 xl:grid-cols-4"
      >
        {branches.map((branch) => {
          const current = branch.key === currentBranchKey;
          const interactive = branch.available && branch.enabled;
          const Icon = stepIcons[branch.key] ?? BookOpenText;
          const content = (
            <>
              <Icon aria-hidden="true" className="size-4 shrink-0" />
              <span className="min-w-0">
                <span className="block truncate text-sm font-semibold">{branch.label}</span>
                <span className="mt-0.5 block text-xs text-[var(--sh-ink-faint)]">
                  {stepStatus(branch, current)}
                </span>
              </span>
            </>
          );

          return interactive ? (
            <Link
              aria-current={current ? "step" : undefined}
              className={stepClass(current, true)}
              key={branch.key}
              to={branch.to}
            >
              {content}
            </Link>
          ) : (
            <div
              aria-current={current ? "step" : undefined}
              className={stepClass(current, false)}
              key={branch.key}
            >
              {content}
            </div>
          );
        })}
      </nav>
    </section>
  );
}
