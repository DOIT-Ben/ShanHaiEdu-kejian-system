import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LessonPlanWorkflowPanel } from "@/features/lessons/components/LessonPlanWorkflowPanel";

const workflow = vi.hoisted(() => ({
  artifact: undefined as Record<string, unknown> | undefined,
  qualityMutate: vi.fn(),
  submitData: undefined as { id: string } | undefined,
  submitIsPending: false,
  submitMutate: vi.fn(),
}));

vi.mock("@/shared/api/client", () => ({
  isCsrfTokenAvailable: () => true,
}));

vi.mock("@/features/artifacts/components/ArtifactWorkbench", () => ({
  ArtifactWorkbench: ({ onSubmit }: { onSubmit?: () => void }) => (
    <button onClick={onSubmit} type="button">
      提交当前草稿
    </button>
  ),
}));

vi.mock("@/features/jobs/components/GenerationJobPanel", () => ({
  GenerationJobPanel: () => null,
}));

vi.mock("@/features/lessons/components/LessonPlanDocument", () => ({
  LessonPlanDocument: () => <div>已提交教案</div>,
  LessonPlanDraftEditor: () => <div>教案草稿</div>,
  lessonPlanContentReady: () => true,
}));

vi.mock("@/features/lessons/hooks/useLessonPlanWorkflow", () => ({
  useLessonPlanApprovalMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useLessonPlanArtifactRuntime: () => ({
    aggregateQuery: { data: { artifact: workflow.artifact }, error: undefined, isLoading: false },
    artifact: workflow.artifact,
    detailQuery: { error: undefined, isLoading: false },
    etag: '"artifact-etag"',
    latestApproval: undefined,
    qualityPendingVersionId: undefined,
    qualityReport: undefined,
    refetchArtifact: vi.fn().mockResolvedValue(undefined),
    setQualityPendingVersionId: vi.fn(),
  }),
  useLessonPlanGenerationMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useLessonPlanJobRuntime: () => ({
    job: undefined,
    jobQuery: { error: undefined, isFetching: false, refetch: vi.fn() },
    jobsQuery: { error: undefined, isLoading: false },
    setStartedJobId: vi.fn(),
  }),
  useLessonPlanQualityMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.qualityMutate,
  }),
  useSaveLessonPlanDraftMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useSubmitLessonPlanDraftMutation: () => ({
    data: workflow.submitData,
    error: undefined,
    isPending: workflow.submitIsPending,
    mutate: workflow.submitMutate,
  }),
}));

function lessonPlanArtifact(submittedVersionId: string) {
  return {
    current_approved_version: undefined,
    current_draft: {
      content: { teaching_content: { topic: "百分数" } },
      draft_branch: "main",
      id: "draft-1",
      lock_version: 1,
    },
    current_submitted_version: {
      content: { teaching_content: { topic: "百分数" } },
      id: submittedVersionId,
      version_no: 2,
    },
    id: "artifact-1",
    status: "in_review",
  };
}

describe("LessonPlanWorkflowPanel", () => {
  beforeEach(() => {
    workflow.artifact = lessonPlanArtifact("version-old");
    workflow.qualityMutate.mockReset();
    workflow.submitData = { id: "version-new" };
    workflow.submitIsPending = true;
    workflow.submitMutate.mockReset();
  });

  it("does not request quality for the stale submitted version while submit refreshes", () => {
    const { rerender } = render(
      <LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />,
    );

    const qualityButton = screen.getByRole("button", { name: "运行质量检查" });
    expect(qualityButton).toBeDisabled();
    fireEvent.click(qualityButton);
    expect(workflow.qualityMutate).not.toHaveBeenCalled();

    workflow.artifact = lessonPlanArtifact("version-new");
    workflow.submitIsPending = false;
    rerender(<LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    expect(qualityButton).toBeEnabled();
    fireEvent.click(qualityButton);
    expect(workflow.qualityMutate).toHaveBeenCalledWith("version-new");
  });
});
