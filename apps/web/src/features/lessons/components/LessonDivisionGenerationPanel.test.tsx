import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LessonDivisionGenerationPanel } from "@/features/lessons/components/LessonDivisionGenerationPanel";

const workflow = vi.hoisted(() => ({
  generationMutate: vi.fn(),
  generationOptions: vi.fn(),
  jobRuntimeProjectId: vi.fn(),
}));

vi.mock("@/shared/api/client", () => ({ isCsrfTokenAvailable: () => true }));
vi.mock("@/features/jobs/components/GenerationJobPanel", () => ({
  GenerationJobPanel: () => <div>任务进度</div>,
}));
vi.mock("@/features/lessons/hooks/useLessonDivisionWorkflow", () => ({
  useLessonDivisionGenerationMutation: (options: unknown) => {
    workflow.generationOptions(options);
    return {
      error: undefined,
      isPending: false,
      mutate: workflow.generationMutate,
    };
  },
  useLessonDivisionJobRuntime: (projectId: string) => {
    workflow.jobRuntimeProjectId(projectId);
    return {
      job: undefined,
      jobQuery: { error: undefined, isFetching: false, refetch: vi.fn() },
      jobsQuery: { error: undefined, isLoading: false },
      setStartedJobId: vi.fn(),
    };
  },
}));

describe("LessonDivisionGenerationPanel", () => {
  beforeEach(() => {
    workflow.generationMutate.mockReset();
    workflow.generationOptions.mockReset();
    workflow.jobRuntimeProjectId.mockReset();
  });

  it("requires an approved exact scope version before generation", () => {
    const { rerender } = render(
      <LessonDivisionGenerationPanel artifactExists={false} projectId="project-1" />,
    );

    expect(screen.getByRole("button", { name: "生成课时划分" })).toBeDisabled();
    expect(screen.getByText("先确认教材范围，再启动课时划分。")).toBeVisible();

    rerender(
      <LessonDivisionGenerationPanel
        artifactExists={false}
        materialScopeVersionId="scope-version-1"
        projectId="project-1"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "生成课时划分" }));

    expect(workflow.generationMutate).toHaveBeenCalledWith("scope-version-1");
    expect(workflow.jobRuntimeProjectId).toHaveBeenCalledWith("project-1");
    expect(workflow.generationOptions).toHaveBeenCalledWith(
      expect.objectContaining({ projectId: "project-1" }),
    );
  });
});
