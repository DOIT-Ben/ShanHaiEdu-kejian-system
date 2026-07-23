import { BookOpen, CheckCircle2, Clock3 } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, buttonVariants } from "@/shared/ui/Button";

export type ProjectLessonSummary = {
  branches: ReadonlyArray<{ enabled: boolean; key: string; label: string; to: string }>;
  durationMinutes?: number;
  id: string;
  scope: string;
  title: string;
};

type ProjectLessonGridProps = {
  emptyMessage?: string;
  errorMessage?: string;
  lessons: readonly ProjectLessonSummary[];
  loading?: boolean;
  onRetry?: () => void;
};

export function ProjectLessonGrid({
  emptyMessage = "当前项目还没有课时。",
  errorMessage,
  lessons,
  loading = false,
  onRetry,
}: ProjectLessonGridProps) {
  return (
    <section aria-labelledby="lesson-list-title">
      <div className="mb-3 flex items-center justify-between gap-3 px-1">
        <h2 className="text-lg font-semibold" id="lesson-list-title">
          课时安排
        </h2>
        <span className="text-sm text-[var(--sh-ink-muted)]">
          {loading ? "读取中" : errorMessage ? "暂不可用" : `${String(lessons.length)} 个课时`}
        </span>
      </div>
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2" role="status">
          {[0, 1].map((item) => (
            <span
              className="h-44 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
              key={item}
            />
          ))}
          <span className="sr-only">正在读取课时</span>
        </div>
      ) : errorMessage ? (
        <div
          className="rounded-[var(--sh-radius-md)] border border-[var(--sh-danger)] bg-[var(--sh-danger-soft)] p-6 text-sm text-[var(--sh-danger)]"
          role="alert"
        >
          <p>{errorMessage}</p>
          {onRetry ? (
            <Button className="mt-4" onClick={onRetry} size="sm" variant="secondary">
              重新读取课时
            </Button>
          ) : null}
        </div>
      ) : lessons.length ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {lessons.map((lesson) => (
            <article
              className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]"
              key={lesson.id}
            >
              <div className="flex items-start justify-between gap-3">
                <span className="grid size-10 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]">
                  <BookOpen aria-hidden="true" className="size-5" />
                </span>
                {lesson.durationMinutes ? (
                  <span className="flex items-center gap-1 text-xs text-[var(--sh-ink-faint)]">
                    <Clock3 aria-hidden="true" className="size-3.5" />
                    {lesson.durationMinutes} 分钟
                  </span>
                ) : null}
              </div>
              <h3 className="mt-3 font-semibold text-[var(--sh-ink-strong)]">{lesson.title}</h3>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
                {lesson.scope}
              </p>
              <div className="mt-4 flex flex-wrap gap-1.5">
                {lesson.branches
                  .filter((branch) => branch.enabled)
                  .map((branch) => (
                    <span
                      className="inline-flex items-center gap-1 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-2.5 py-1 text-xs text-[var(--sh-ink-muted)]"
                      key={branch.key}
                    >
                      <CheckCircle2
                        aria-hidden="true"
                        className="size-3 text-[var(--sh-success)]"
                      />
                      {branch.label}
                    </span>
                  ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {lesson.branches
                  .filter((branch) => branch.enabled)
                  .map((branch) => (
                    <Link
                      className={buttonVariants({ size: "sm", variant: "secondary" })}
                      key={branch.key}
                      to={branch.to}
                    >
                      查看{branch.label}
                    </Link>
                  ))}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-8 text-center text-sm text-[var(--sh-ink-muted)]">
          {emptyMessage}
        </div>
      )}
    </section>
  );
}
