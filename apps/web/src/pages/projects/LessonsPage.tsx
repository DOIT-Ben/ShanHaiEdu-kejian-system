import { ArrowRight, BookOpen, Clock3 } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getApprovedProjectLessons } from "@/features/workbench/lib/projectLessons";
import { useMockRuntime } from "@/shared/api/mockClient";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";

export function LessonsPage() {
  const { projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const lessonItems = getApprovedProjectLessons(runtime, projectId);
  return (
    <div className="mx-auto max-w-[1200px] px-4 py-4 md:px-6">
      <FocusPageHeader
        description="每个课时独立拥有教案，以及可选的 PPT 和课堂导入视频。"
        title="课时工作台"
      />
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {lessonItems.map((lesson, index) => (
          <article
            className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4"
            key={lesson.id}
          >
            <div className="flex flex-wrap items-start gap-4">
              <span className="grid size-10 shrink-0 place-items-center rounded-[var(--sh-radius-sm)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-600)]">
                <BookOpen aria-hidden="true" className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-[var(--sh-brand-600)]">课时 {index + 1}</p>
                <h2 className="mt-1 text-lg font-bold text-[var(--sh-ink-strong)]">
                  {lesson.title}
                </h2>
                <p className="mt-1.5 text-sm text-[var(--sh-ink-muted)]">{lesson.scope}</p>
                <p className="mt-2 flex items-center gap-1.5 text-xs text-[var(--sh-ink-faint)]">
                  <Clock3 aria-hidden="true" className="size-3.5" />
                  {lesson.duration} 分钟
                </p>
              </div>
              <Button asChild>
                <Link to={`/app/projects/${projectId}/lessons/${lesson.id}/work/lesson-plan`}>
                  进入课时
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Link>
              </Button>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 border-t border-[var(--sh-line-subtle)] pt-3">
              {(
                [
                  ["教案", lesson.planStatus],
                  ["课堂导入", lesson.introStatus],
                  ["PPT", lesson.pptStatus],
                  ["导入视频", lesson.videoStatus],
                ] as const
              ).map(([label, status]) => (
                <div
                  className="flex items-center justify-between gap-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] px-2.5 py-2"
                  key={label}
                >
                  <span className="text-sm font-medium text-[var(--sh-ink-default)]">{label}</span>
                  <StatusBadge status={status} />
                </div>
              ))}
            </div>
          </article>
        ))}
        {lessonItems.length === 0 ? (
          <p className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)] lg:col-span-2">
            课时安排批准后会显示在这里。
          </p>
        ) : null}
      </div>
    </div>
  );
}
