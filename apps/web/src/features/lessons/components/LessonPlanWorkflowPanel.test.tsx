import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";
import { LessonPlanWorkflowPanel } from "@/features/lessons/components/LessonPlanWorkflowPanel";
import goldenProject from "../../../../../../contracts/fixtures/golden-projects/numbers-1-to-5/golden-project.json";

const workflow = vi.hoisted(() => ({
  artifact: undefined as Record<string, unknown> | undefined,
  job: undefined as GenerationJobDto | undefined,
  qualityMutate: vi.fn(),
  saveReset: vi.fn(),
  saveMutate: vi.fn(),
  submitData: undefined as { id: string } | undefined,
  submitIsPending: false,
  submitMutate: vi.fn(),
}));

vi.mock("@/shared/api/client", () => ({
  isCsrfTokenAvailable: () => true,
}));

vi.mock("@/features/artifacts/components/ArtifactWorkbench", () => ({
  ArtifactWorkbench: ({
    contentNavigation,
    draftEditor,
    onSaveDraft,
    onSubmit,
    reviewStatus,
  }: {
    contentNavigation?: React.ReactNode;
    draftEditor?: React.ReactNode;
    onSaveDraft?: () => void;
    onSubmit?: () => void;
    reviewStatus?: React.ReactNode;
  }) => (
    <div>
      {contentNavigation}
      {draftEditor}
      {reviewStatus}
      <button onClick={onSaveDraft} type="button">
        保存当前草稿
      </button>
      <button onClick={onSubmit} type="button">
        提交当前草稿
      </button>
    </div>
  ),
}));

vi.mock("@/features/jobs/components/GenerationJobPanel", () => ({
  GenerationJobPanel: () => null,
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
    job: workflow.job,
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
    mutate: workflow.saveMutate,
    reset: workflow.saveReset,
  }),
  useSubmitLessonPlanDraftMutation: () => ({
    data: workflow.submitData,
    error: undefined,
    isPending: workflow.submitIsPending,
    mutate: workflow.submitMutate,
  }),
}));

function lessonPlanArtifact(
  submittedVersionId: string,
  content: Record<string, unknown> = { teaching_content: { topic: "百分数" } },
) {
  return {
    current_approved_version: undefined,
    current_draft: {
      content,
      draft_branch: "main",
      id: "draft-1",
      lock_version: 1,
    },
    current_submitted_version: {
      content,
      id: submittedVersionId,
      version_no: 2,
    },
    id: "artifact-1",
    status: "in_review",
  };
}

const goldenSections = goldenProject.lesson_plan.sections;
const goldenLessonPlanContent = {
  ...goldenSections,
  teaching_content: {
    ...goldenSections.teaching_content,
    grade: goldenProject.project.grade,
    lesson_plan_key: goldenProject.lesson_plan.lesson_plan_key,
    lesson_topic: goldenSections.teaching_content.topic,
    source_lesson_unit_key: goldenProject.lesson_plan.source_lesson_unit_key,
    subject: goldenProject.project.subject,
    teaching_scope: goldenSections.teaching_content.scope,
  },
  teaching_reflection: {
    reflection_prompts: goldenSections.teaching_reflection.prompts,
    reflection_state: goldenSections.teaching_reflection.state,
    teacher_reflection_record: goldenSections.teaching_reflection.teacher_record,
  },
};

describe("LessonPlanWorkflowPanel", () => {
  beforeEach(() => {
    workflow.artifact = lessonPlanArtifact("version-old");
    workflow.job = undefined;
    workflow.qualityMutate.mockReset();
    workflow.saveReset.mockReset();
    workflow.saveMutate.mockReset();
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

  it("keeps golden lesson identity fields locked in the saved draft", () => {
    workflow.artifact = lessonPlanArtifact("version-golden", goldenLessonPlanContent);
    workflow.submitData = undefined;
    workflow.submitIsPending = false;
    render(<LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    expect(screen.queryByDisplayValue(goldenProject.project.subject)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(goldenProject.project.grade)).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/一、教学内容 教学范围/), {
      target: { value: "调整后的本课教学范围" },
    });
    expect(workflow.saveReset).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "保存当前草稿" }));

    expect(workflow.saveMutate).toHaveBeenCalledWith({
      ...goldenLessonPlanContent,
      teaching_content: {
        ...goldenLessonPlanContent.teaching_content,
        teaching_scope: "调整后的本课教学范围",
      },
    });
  });

  it("provides a twelve-part document outline and keeps review actions together", () => {
    workflow.artifact = lessonPlanArtifact("version-golden", goldenLessonPlanContent);
    workflow.submitData = undefined;
    workflow.submitIsPending = false;

    render(<LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    const outline = screen.getByRole("navigation", { name: "教案十二部分目录" });
    expect(outline).toBeVisible();
    expect(screen.getByRole("link", { name: "一、教学内容" })).toHaveAttribute(
      "href",
      "#lesson-plan-section-teaching_content",
    );
    expect(screen.getByRole("link", { name: "十二、教学反思" })).toHaveAttribute(
      "href",
      "#lesson-plan-section-teaching_reflection",
    );
    expect(screen.getByRole("button", { name: "运行质量检查" })).toBeVisible();
  });

  it("keeps the empty workbench aligned with the running generation job", () => {
    workflow.artifact = undefined;
    workflow.job = generationJob("running");
    workflow.submitData = undefined;
    workflow.submitIsPending = false;

    render(<LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    expect(screen.getByRole("heading", { name: "正在生成教案" })).toBeVisible();
    expect(screen.getByRole("button", { name: "正在生成" })).toBeDisabled();
    expect(screen.getByText("进行中")).toBeVisible();
    expect(screen.queryByText("尚未生成")).not.toBeInTheDocument();
    expect(screen.queryByText("待开始")).not.toBeInTheDocument();
  });

  it("offers an explicit retry after the generation job fails", () => {
    workflow.artifact = undefined;
    workflow.job = generationJob("failed");
    workflow.submitData = undefined;
    workflow.submitIsPending = false;

    render(<LessonPlanWorkflowPanel lessonId="lesson-1" projectId="project-1" />);

    expect(screen.getByRole("heading", { name: "教案生成未完成" })).toBeVisible();
    expect(screen.getByRole("button", { name: "重新生成十二部分教案" })).toBeEnabled();
    expect(screen.getByText("未完成")).toBeVisible();
  });
});

function generationJob(status: GenerationJobDto["status"]): GenerationJobDto {
  return {
    created_at: "2030-01-01T00:00:00Z",
    error_code: status === "failed" ? "MODEL_TIMEOUT" : null,
    id: "job-lesson-plan",
    job_type: "lesson_plan_generation",
    lesson_unit_id: "lesson-1",
    node_run_id: null,
    progress_message: status === "failed" ? "生成超时" : "正在生成教学过程",
    progress_percent: status === "failed" ? 62 : 46,
    project_id: "project-1",
    result_artifact_version_id: null,
    status,
    updated_at: "2030-01-01T00:01:00Z",
    workflow_node_key: null,
  };
}
