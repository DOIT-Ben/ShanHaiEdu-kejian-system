import { useInfiniteQuery, type InfiniteData } from "@tanstack/react-query";
import { listProjectsPage, type ProjectListPage } from "@/features/projects/api/projectsApi";
import { mapProjectSummary } from "@/features/projects/mappers/projectMapper";

export const projectKeys = {
  all: ["projects"] as const,
  detail: (projectId: string) => ["projects", projectId] as const,
  workflow: (projectId: string) => ["projects", projectId, "workflow"] as const,
};

export function useProjectsQuery() {
  const query = useInfiniteQuery<
    ProjectListPage,
    Error,
    InfiniteData<ProjectListPage>,
    typeof projectKeys.all,
    string | undefined
  >({
    getNextPageParam: (lastPage) => lastPage.nextCursor,
    initialPageParam: undefined as string | undefined,
    queryKey: projectKeys.all,
    queryFn: ({ pageParam }) => listProjectsPage(pageParam),
  });
  return {
    ...query,
    data: query.data?.pages.flatMap((page) => page.items.map(mapProjectSummary)),
  };
}
