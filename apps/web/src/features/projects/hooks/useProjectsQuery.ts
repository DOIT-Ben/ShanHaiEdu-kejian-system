import { useInfiniteQuery, type InfiniteData } from "@tanstack/react-query";
import { listProjectsPage, type ProjectListPage } from "@/features/projects/api/projectsApi";
import { mapProjectSummary } from "@/features/projects/mappers/projectMapper";
import { apiConfig } from "@/shared/api/config";
import { useMockRuntime } from "@/shared/api/mocks/runtime";

export const projectKeys = {
  all: ["projects"] as const,
  detail: (projectId: string) => ["projects", projectId] as const,
  workflow: (projectId: string) => ["projects", projectId, "workflow"] as const,
};

export function useProjectsQuery() {
  const mockProjects = useMockRuntime((state) => state.projects);
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
    enabled: apiConfig.mode !== "mock",
  });
  if (apiConfig.mode === "mock") {
    return {
      ...query,
      data: mockProjects.map(mapProjectSummary),
      hasNextPage: false,
      isError: false,
      isFetching: false,
      isLoading: false,
    };
  }
  return {
    ...query,
    data: query.data?.pages.flatMap((page) => page.items.map(mapProjectSummary)),
  };
}
