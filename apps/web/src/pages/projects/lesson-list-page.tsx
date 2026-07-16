import { Link, useOutletContext } from "react-router";
import { ArrowRight, ListTodo } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useLessons } from "@/features/lessons";
import type { NodeStatus } from "@/shared/lib/status";
import { EmptyState, NodeStatusBadge, PageHeader, Skeleton } from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const STAGE_LABEL: Record<string, string> = {
  lesson_plan: "教案",
  intro_design: "导入",
  ppt: "PPT",
  video: "视频",
  delivery: "交付",
};

/** 课时列表页：每课时五阶段状态一览，点击进入工作台。 */
export function LessonListPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const lessons = useLessons(project.project_id);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="课时" description="每个课时都有独立的 18 步制作流程；从任意课时进入工作台继续制作。" />
      {lessons.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      ) : lessons.isError ? (
        <AppErrorPanel error={lessons.error} title="课时加载失败" onRetry={() => void lessons.refetch()} />
      ) : (lessons.data ?? []).length === 0 ? (
        <EmptyState
          icon={<ListTodo className="size-8" aria-hidden />}
          title="还没有课时"
          description="在「课时划分」页确认划分后，课时会自动创建。"
          action={
            <Link to="../lesson-division" className="text-sm font-medium text-brand hover:underline">
              前往课时划分
            </Link>
          }
        />
      ) : (
        <ul className="space-y-2">
          {(lessons.data ?? []).map((lesson) => (
            <li key={lesson.lesson_id}>
              <Link
                to={`${lesson.lesson_id}`}
                className="flex items-center gap-4 rounded-card border border-line bg-surface-1 px-4 py-3 transition-colors hover:bg-surface-hover"
              >
                <span className="w-16 shrink-0 text-xs text-ink-muted">第{lesson.sequence_number}课时</span>
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink-1">{lesson.title}</span>
                <span className="hidden flex-wrap items-center gap-x-3 gap-y-1 md:flex">
                  {(Object.keys(STAGE_LABEL) as Array<keyof typeof STAGE_LABEL>).map((stage) => {
                    const status = lesson.stage_summary?.[stage as keyof NonNullable<typeof lesson.stage_summary>];
                    if (!status) return null;
                    return (
                      <span key={stage} className="flex items-center gap-1 text-xs text-ink-muted">
                        {STAGE_LABEL[stage]}
                        <NodeStatusBadge status={status as NodeStatus} />
                      </span>
                    );
                  })}
                </span>
                <ArrowRight className="size-4 shrink-0 text-ink-muted" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
