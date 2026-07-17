import { JobList, useJobs } from "@/features/generation-tasks";
import { PageHeader, Skeleton } from "@/shared/ui";

/** 任务中心：全部项目的生成任务总览（SSE 驱动自动更新）。 */
export default function TaskCenterPage() {
  const { data: jobs, isPending } = useJobs({});

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <PageHeader title="任务中心" description="所有项目的生成任务。完成后会自动更新，无需手动刷新。" />
      <div className="mt-6">
        {isPending ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-lg" />
            ))}
          </div>
        ) : (
          <JobList jobs={jobs ?? []} emptyHint="现在没有任务。去项目里开始创作吧。" />
        )}
      </div>
    </div>
  );
}
