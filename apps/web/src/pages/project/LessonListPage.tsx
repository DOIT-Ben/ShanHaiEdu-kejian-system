import { Link, useParams } from "react-router";
import { ArrowRight } from "lucide-react";
import { useLessons } from "@/features/projects";
import { getBranchStateMeta } from "@/shared/lib/status";
import { Badge, EmptyState, PageHeader, Skeleton, Button } from "@/shared/ui";

/** 课时工作台入口：选择课时进入分步创作。 */
export default function LessonListPage() {
  const { projectId = "" } = useParams();
  const { data: lessons, isPending } = useLessons(projectId);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <PageHeader
        title="课时工作台"
        description="选择一个课时，按步骤完成教案、课堂导入、PPT 与导入视频。"
      />
      {isPending ? (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
      ) : lessons && lessons.length > 0 ? (
        <ul className="mt-6 space-y-3">
          {lessons.map((lesson) => {
            const branches = [
              ["教案", lesson.branches.lesson_plan],
              ["课堂导入", lesson.branches.intro_options],
              ["PPT", lesson.branches.ppt],
              ["导入视频", lesson.branches.video],
            ] as const;
            const actionable = branches.find(
              ([, b]) => b.state === "review_required" || b.state === "stale" || b.state === "in_progress",
            );
            return (
              <li key={lesson.id}>
                <Link
                  to={`/app/projects/${projectId}/lessons/${lesson.id}`}
                  className="flex flex-wrap items-center gap-4 rounded-lg border border-line-subtle bg-surface p-5 shadow-card transition-shadow duration-150 hover:shadow-floating"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-600">
                    {lesson.position}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-base font-semibold text-ink-strong">{lesson.title}</span>
                    <span className="mt-0.5 block truncate text-sm text-ink-muted">
                      {actionable?.[1].summary ?? lesson.focus}
                    </span>
                  </span>
                  <span className="flex flex-wrap items-center gap-1.5">
                    {branches.map(([label, branch]) => {
                      const meta = getBranchStateMeta(branch.state);
                      return (
                        <Badge key={label} tone={meta.tone}>
                          {label}·{meta.label}
                        </Badge>
                      );
                    })}
                  </span>
                  <ArrowRight className="size-4 shrink-0 text-ink-faint" aria-hidden />
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <EmptyState
          className="mt-6"
          title="还没有课时"
          description="先在「教材与课时」完成教材上传与课时划分批准。"
          action={
            <Button asChild variant="secondary">
              <Link to={`/app/projects/${projectId}/materials`}>去教材与课时</Link>
            </Button>
          }
        />
      )}
    </div>
  );
}
