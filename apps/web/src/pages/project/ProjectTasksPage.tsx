import { useParams } from "react-router";
import { JobList, useJobs } from "@/features/generation-tasks";
import { PageHeader, Skeleton } from "@/shared/ui";

/** 项目任务：本项目的生成任务（进行中在前）。 */
export default function ProjectTasksPage() {
  const { projectId = "" } = useParams();
  const { data: jobs, isPending } = useJobs({ projectId });

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <PageHeader title="项目任务" description="本项目里正在进行和已完成的生成任务。" />
      <div className="mt-6">
        {isPending ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 rounded-lg" />
            ))}
          </div>
        ) : (
          <JobList jobs={jobs ?? []} emptyHint="开始生成教案、PPT 或视频后，任务会出现在这里。" />
        )}
      </div>
    </div>
  );
}
