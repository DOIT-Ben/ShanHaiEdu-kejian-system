import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { IntroOptionsWorkflowPanel } from "@/features/intro-options/components/IntroOptionsWorkflowPanel";
import goldenProject from "../../../../../../contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json";

const workflow = vi.hoisted(() => ({
  artifact: undefined as Record<string, unknown> | undefined,
  latestApproval: undefined as Record<string, unknown> | undefined,
  qualityMutate: vi.fn(),
  qualityReport: undefined as Record<string, unknown> | undefined,
}));

vi.mock("@/shared/api/client", () => ({ isCsrfTokenAvailable: () => true }));
vi.mock("@/features/jobs/components/GenerationJobPanel", () => ({
  GenerationJobPanel: () => null,
}));
vi.mock("@/features/intro-options/components/ApprovedIntroOptionSelection", () => ({
  ApprovedIntroOptionSelection: () => <div data-testid="approved-selection" />,
}));
vi.mock("@/features/intro-options/components/IntroOptionSetDocument", () => ({
  IntroOptionSetDocument: () => <div data-testid="intro-option-set" />,
}));
vi.mock("@/features/artifacts/components/ArtifactWorkbench", () => ({
  ArtifactWorkbench: ({ draftEditor }: { draftEditor?: React.ReactNode }) => (
    <div>{draftEditor}</div>
  ),
}));
vi.mock("@/features/intro-options/hooks/useIntroOptionsWorkflow", () => ({
  useIntroOptionSelectionMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
    variables: undefined,
  }),
  useIntroOptionsApprovalMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useIntroOptionsArtifactRuntime: () => ({
    aggregateQuery: { data: { artifact: workflow.artifact }, error: undefined, isLoading: false },
    artifact: workflow.artifact,
    detailQuery: { error: undefined, isLoading: false },
    etag: 'W/"artifact-etag"',
    latestApproval: workflow.latestApproval,
    publicQuery: { data: undefined, isLoading: false },
    qualityPendingVersionId: undefined,
    qualityReport: workflow.qualityReport,
    refetchArtifact: vi.fn().mockResolvedValue(undefined),
    setQualityPendingVersionId: vi.fn(),
  }),
  useIntroOptionsGenerationMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useIntroOptionsJobRuntime: () => ({
    job: undefined,
    jobQuery: { error: undefined, isFetching: false, refetch: vi.fn() },
    jobsQuery: { error: undefined, isLoading: false },
    setStartedJobId: vi.fn(),
  }),
  useIntroOptionsQualityMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.qualityMutate,
  }),
  useSaveIntroOptionsDraftMutation: () => ({ error: undefined, isPending: false }),
  useSubmitIntroOptionsDraftMutation: () => ({
    data: undefined,
    error: undefined,
    isPending: false,
  }),
}));

function artifact(submittedVersionId: string, approvedVersionId: string) {
  const content = goldenProject.intro_option_set;
  return {
    current_approved_version: { content, id: approvedVersionId, version_no: 1 },
    current_draft: { content, draft_branch: "main", id: "draft-1", lock_version: 2 },
    current_submitted_version: { content, id: submittedVersionId, version_no: 2 },
    id: "artifact-1",
    status: "in_review",
  };
}

describe("IntroOptionsWorkflowPanel", () => {
  beforeEach(() => {
    workflow.artifact = artifact("version-new", "version-old");
    workflow.latestApproval = { action: "approve", artifact_version_id: "version-old" };
    workflow.qualityMutate.mockReset();
    workflow.qualityReport = undefined;
  });

  it("allows quality validation for a new submission while an older version remains approved", () => {
    render(<IntroOptionsWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    const qualityButton = screen.getByRole("button", { name: "运行质量检查" });
    expect(qualityButton).toBeEnabled();
    fireEvent.click(qualityButton);
    expect(workflow.qualityMutate).toHaveBeenCalledWith("version-new");
    expect(screen.getByTestId("approved-selection")).toBeVisible();
  });

  it("marks quality as complete only for the exact submitted version", () => {
    workflow.qualityReport = {
      artifact_version_id: "version-old",
      conclusion: "passed",
    };
    render(<IntroOptionsWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    expect(screen.getByRole("button", { name: "运行质量检查" })).toBeEnabled();
    expect(screen.queryByText("检查通过，可以批准当前版本")).not.toBeInTheDocument();
  });
});
