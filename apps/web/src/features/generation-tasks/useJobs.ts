import { useQuery } from "@tanstack/react-query";
import { client, unwrap, qk } from "@/shared/api";
import { isTaskActive } from "@/shared/lib/status";

/** 任务中心共享查询。 */
export function useJobs(filters?: { projectId?: string; active?: boolean }) {
  return useQuery({
    queryKey: qk.jobs.list({
      ...(filters?.projectId ? { project_id: filters.projectId } : {}),
      ...(filters?.active ? { active: true } : {}),
    }),
    queryFn: async () => {
      const result = unwrap(
        await client.GET("/generation-jobs", {
          params: {
            query: {
              ...(filters?.projectId ? { project_id: filters.projectId } : {}),
              ...(filters?.active ? { active: true } : {}),
            },
          },
        }),
      );
      return result.data.items;
    },
    refetchInterval: (query) => {
      const items = query.state.data;
      return items?.some((job) => isTaskActive(job.status)) ? 5_000 : false;
    },
  });
}

export function useActiveJobCount(): number {
  const { data } = useJobs({ active: true });
  return data?.length ?? 0;
}
