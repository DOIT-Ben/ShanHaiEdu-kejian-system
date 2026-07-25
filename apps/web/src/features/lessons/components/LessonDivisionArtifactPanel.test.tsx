import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LessonDivisionArtifactPanel } from "@/features/lessons/components/LessonDivisionArtifactPanel";

const workflow = vi.hoisted(() => ({
  approvalMutate: vi.fn(),
  qualityMutate: vi.fn(),
  submitData: undefined as { id: string } | undefined,
  submitPending: false,
}));

vi.mock("@/shared/api/client", () => ({ isCsrfTokenAvailable: () => true }));
vi.mock("@/features/artifacts/components/ArtifactWorkbench", () => ({
  ArtifactWorkbench: ({
    onApprove,
    onSubmit,
  }: {
    onApprove?: () => void;
    onSubmit?: () => void;
  }) => (
    <div>
      <button onClick={onSubmit} type="button">
        提交当前草稿
      </button>
      {onApprove ? (
        <button onClick={onApprove} type="button">
          批准当前版本
        </button>
      ) : null}
    </div>
  ),
}));
vi.mock("@/features/lessons/hooks/useLessonDivisionWorkflow", () => ({
  useLessonDivisionApprovalMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.approvalMutate,
  }),
  useLessonDivisionQualityMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: workflow.qualityMutate,
  }),
  useSaveLessonDivisionDraftMutation: () => ({
    error: undefined,
    isPending: false,
    mutate: vi.fn(),
  }),
  useSubmitLessonDivisionDraftMutation: () => ({
    data: workflow.submitData,
    error: undefined,
    isPending: workflow.submitPending,
    mutate: vi.fn(),
  }),
}));

const content = {
  lesson_count: 1,
  lesson_units: [{ lesson_unit_key: "LESSON-001", title: "认识1到5" }],
};

function artifact(versionId: string) {
  return {
    current_approved_version: null,
    current_draft: { content, draft_branch: "main", id: "draft-1", lock_version: 1 },
    current_submitted_version: { content, id: versionId, version_no: 2 },
    id: "artifact-1",
    status: "in_review",
  };
}

function runtime(versionId: string, qualityPassed = false) {
  return {
    aggregateQuery: {
      data: { artifact: { id: "artifact-1" } },
      error: undefined,
      isLoading: false,
    },
    artifact: artifact(versionId),
    detailQuery: { error: undefined, isLoading: false },
    etag: '"artifact-etag"',
    qualityPendingVersionId: undefined,
    qualityReport: qualityPassed
      ? { artifact_version_id: versionId, conclusion: "passed" }
      : undefined,
    refetch: vi.fn().mockResolvedValue(undefined),
    setQualityPendingVersionId: vi.fn(),
  } as never;
}

describe("LessonDivisionArtifactPanel", () => {
  beforeEach(() => {
    workflow.approvalMutate.mockReset();
    workflow.qualityMutate.mockReset();
    workflow.submitData = undefined;
    workflow.submitPending = false;
  });

  it("does not validate a stale submitted version while submit refreshes", () => {
    workflow.submitData = { id: "version-new" };
    workflow.submitPending = true;
    render(
      <LessonDivisionArtifactPanel
        approved={false}
        projectId="project-1"
        runtime={runtime("version-old")}
      />,
    );

    const qualityButton = screen.getByRole("button", { name: "运行质量检查" });
    expect(qualityButton).toBeDisabled();
    fireEvent.click(qualityButton);
    expect(workflow.qualityMutate).not.toHaveBeenCalled();
  });

  it("restores passed quality and exact approval actions from runtime facts", () => {
    render(
      <LessonDivisionArtifactPanel
        approved={false}
        projectId="project-1"
        runtime={runtime("version-1", true)}
      />,
    );

    expect(screen.getByText("检查通过，可以批准当前版本")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "批准当前版本" }));
    expect(workflow.approvalMutate).toHaveBeenCalledOnce();
  });
});
