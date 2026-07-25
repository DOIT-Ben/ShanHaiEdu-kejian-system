import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import { useLessonPlanJobRuntime } from "@/features/lessons/hooks/useLessonPlanWorkflow";
import * as workflowApi from "@/features/workflow/api/workflowApi";

vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

function LessonJobProbe({ lessonId, projectId }: { lessonId: string; projectId: string }) {
  useLessonPlanJobRuntime(projectId, lessonId);
  return null;
}

describe("useLessonPlanJobRuntime", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps generation-job list queries isolated by exact lesson", async () => {
    const projectId = "01960000-0000-7000-8000-000000000001";
    const lessonOneId = "01960000-0000-7000-8000-000000000002";
    const lessonTwoId = "01960000-0000-7000-8000-000000000003";
    vi.spyOn(workflowApi, "getProjectWorkflow").mockResolvedValue({
      lessons: [],
      node_runs: [],
    } as unknown as workflowApi.WorkflowDto);
    const listJobs = vi.spyOn(jobsApi, "listProjectGenerationJobsPage").mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <LessonJobProbe lessonId={lessonOneId} projectId={projectId} />
        <LessonJobProbe lessonId={lessonTwoId} projectId={projectId} />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(listJobs).toHaveBeenCalledTimes(2));
    expect(listJobs).toHaveBeenCalledWith({
      lessonId: lessonOneId,
      limit: 100,
      projectId,
    });
    expect(listJobs).toHaveBeenCalledWith({
      lessonId: lessonTwoId,
      limit: 100,
      projectId,
    });
  });
});
