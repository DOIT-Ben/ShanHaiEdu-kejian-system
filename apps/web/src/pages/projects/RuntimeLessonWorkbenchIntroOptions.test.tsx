import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as artifactsApi from "@/features/artifacts/api/artifactsApi";
import * as introOptionsApi from "@/features/intro-options/api/introOptionsApi";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import * as workflowApi from "@/features/workflow/api/workflowApi";
import { RuntimeLessonWorkbenchPage } from "@/pages/projects/RuntimeLessonWorkbenchPage";
import { ApiError, configureCsrfTokenProvider } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000201";
const lessonId = "01960000-0000-7000-8000-000000000202";
const artifactId = "01960000-0000-7000-8000-000000000203";
const artifactVersionId = "01960000-0000-7000-8000-000000000204";
const nodeRunId = "01960000-0000-7000-8000-000000000205";
const jobId = "01960000-0000-7000-8000-000000000206";
const qualityNodeRunId = "01960000-0000-7000-8000-000000000210";

type IntroOptionDto = NonNullable<
  introOptionsApi.IntroOptionsDto["display_version"]
>["option_set"]["options"][number];
type IntroOptionVersionDto = NonNullable<introOptionsApi.IntroOptionsDto["display_version"]>;

const tendencyConfig = {
  application: { code: "APP", label: "应用" },
  science: { code: "SCI", label: "科普" },
  story: { code: "STO", label: "故事" },
} as const;

function makeIntroOption(
  tendency: keyof typeof tendencyConfig,
  index: number,
  score: number,
): IntroOptionDto {
  const config = tendencyConfig[tendency];
  const secondary = tendency === "science" ? "application" : "science";
  return {
    classroom_first_question: `请观察${config.label}方案 ${String(index)} 的关键线索。`,
    course_anchor: "严格回到百分数表示两个数量关系的本课边界。",
    creative_concept: `${config.label}方案 ${String(index)} 的创意情境。`,
    duration_seconds: 45,
    fit_reason: "与当前课时知识点和教材证据直接关联。",
    handoff_moment: "在结论出现前停住并交回课堂。",
    hook: `为什么会出现${config.label}线索？`,
    knowledge_point: "百分数的意义",
    lesson_unit_key: "lesson-1",
    must_not_preteach: ["百分数的完整定义"],
    option_key: `INTRO-${config.code}-${String(index).padStart(2, "0")}`,
    primary_tendency: tendency,
    recommendation_reason: "课程锚点清晰且课堂交接自然。",
    recommendation_score: score,
    risks: [],
    secondary_tendencies: [secondary],
    suggested_medium: "video",
    title: `${config.label}方案 ${String(index)}`,
    viewer_value: "学生能从可观察线索提出本课问题。",
  };
}

const recommendedOption = makeIntroOption("science", 1, 99);
const introOptions: IntroOptionDto[] = [
  recommendedOption,
  makeIntroOption("science", 2, 90),
  makeIntroOption("science", 3, 81),
  makeIntroOption("application", 1, 96),
  makeIntroOption("application", 2, 87),
  makeIntroOption("application", 3, 78),
  makeIntroOption("story", 1, 93),
  makeIntroOption("story", 2, 84),
  makeIntroOption("story", 3, 75),
];

const pendingVersion = {
  approval_status: "pending_review",
  artifact_version_id: artifactVersionId,
  option_set: {
    created_at: "2030-01-01T00:00:00Z",
    generation_mode: "default_nine",
    knowledge_point: "百分数的意义",
    lesson_unit_key: "lesson-1",
    options: introOptions,
  },
  selectable: false,
  stale: false,
  version_no: 1,
} satisfies IntroOptionVersionDto;

const approvedVersion = {
  ...pendingVersion,
  approval_status: "approved",
  selectable: true,
} satisfies IntroOptionVersionDto;

const pendingOptions = {
  artifact_id: artifactId,
  current_approved_version_id: null,
  current_selection: null,
  display_version: null,
  pending_version: pendingVersion,
} satisfies introOptionsApi.IntroOptionsDto;

const approvedOptions = {
  artifact_id: artifactId,
  current_approved_version_id: artifactVersionId,
  current_selection: null,
  display_version: approvedVersion,
  pending_version: null,
} satisfies introOptionsApi.IntroOptionsDto;

const selection = {
  active: true,
  artifact_version_id: artifactVersionId,
  consumable: true,
  deactivated_at: null,
  option_key: recommendedOption.option_key,
  reason: "teacher_selected",
  selected_at: "2030-01-01T00:00:01Z",
  selection_id: "01960000-0000-7000-8000-000000000207",
  selection_method: "teacher_selected",
  snapshot: recommendedOption,
  unconsumable_reason: null,
} satisfies introOptionsApi.IntroSelectionDto;

const selectedOptions = {
  ...approvedOptions,
  current_selection: selection,
} satisfies introOptionsApi.IntroOptionsDto;

const runningIntroJob = {
  created_at: "2030-01-01T00:00:00Z",
  id: jobId,
  job_type: "workflow.node",
  lesson_unit_id: lessonId,
  node_run_id: nodeRunId,
  progress_message: "正在生成三类九套",
  progress_percent: 35,
  project_id: projectId,
  result_artifact_version_id: null,
  status: "running",
  updated_at: "2030-01-01T00:00:01Z",
} as jobsApi.GenerationJobDto;

function missingIntroOptionsError() {
  return new ApiError({
    error: {
      code: "INTRO_OPTIONS_NOT_FOUND",
      message: "The Intro option set was not found.",
      retryable: false,
    },
    request_id: "intro-options-missing",
  });
}

function renderIntroPage() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[`/app/projects/${projectId}/lessons/${lessonId}/work/intro_options`]}
      >
        <Routes>
          <Route
            element={<RuntimeLessonWorkbenchPage />}
            path="/app/projects/:projectId/lessons/:lessonId/work/:stepKey"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeLessonWorkbenchPage Intro options", () => {
  beforeEach(() => {
    configureCsrfTokenProvider(() => "csrf-test-token");
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      id: projectId,
      title: "认识百分数",
    } as Awaited<ReturnType<typeof projectsApi.getProject>>);
    vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      lesson: {
        branches: [
          { branch_key: "lesson_plan", enabled: true, settings: {}, workflow_status: "approved" },
          {
            branch_key: "intro_options",
            enabled: true,
            settings: {},
            workflow_status: "not_ready",
          },
        ],
        estimated_minutes: 40,
        id: lessonId,
        lesson_key: "lesson-1",
        objective_summary: "理解百分数表示两个数量之间的关系。",
        project_id: projectId,
        scope_summary: "认识百分数并能正确读写。",
        title: "百分数的意义",
      },
    } as Awaited<ReturnType<typeof lessonsApi.getLesson>>);
    vi.spyOn(introOptionsApi, "getLessonIntroOptions").mockRejectedValue(
      missingIntroOptionsError(),
    );
    vi.spyOn(jobsApi, "listProjectGenerationJobsPage").mockResolvedValue({
      items: [],
      nextCursor: null,
    });
    vi.spyOn(workflowApi, "getProjectWorkflow").mockResolvedValue({
      lessons: [],
      node_runs: [],
    } as unknown as workflowApi.WorkflowDto);
  });

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("无现有方案时通过正式节点生成默认三类九套", async () => {
    const prepare = vi.spyOn(workflowApi, "prepareIntroOptionGeneration").mockResolvedValue({
      id: nodeRunId,
      node_key: "intro.generate_options",
      status: "ready",
    });
    const start = vi.spyOn(workflowApi, "startNodeRun").mockResolvedValue({
      events_url: `/api/v2/generation-jobs/${jobId}/events/stream`,
      job_id: jobId,
      status: "queued",
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(runningIntroJob);
    const user = userEvent.setup();
    renderIntroPage();

    await user.click(await screen.findByRole("button", { name: "生成三类九套" }));

    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(prepare).toHaveBeenCalledWith(
      expect.objectContaining({ generationMode: "default_nine", lessonId }),
    );
    expect(start).toHaveBeenCalledWith(expect.objectContaining({ nodeRunId }));
    expect(await screen.findByRole("heading", { name: "任务正在处理" })).toBeVisible();
    expect(vi.mocked(useJobEvents)).toHaveBeenCalledWith(jobId, projectId);
  });

  it("刷新时只恢复属于当前课时的 Intro 生成 Job", async () => {
    const otherJob = {
      ...runningIntroJob,
      id: "01960000-0000-7000-8000-000000000208",
      node_run_id: "01960000-0000-7000-8000-000000000209",
    };
    vi.mocked(jobsApi.listProjectGenerationJobsPage).mockResolvedValue({
      items: [otherJob, runningIntroJob],
      nextCursor: null,
    });
    vi.mocked(workflowApi.getProjectWorkflow).mockResolvedValue({
      lessons: [],
      node_runs: [
        { id: otherJob.node_run_id, node_key: "lesson_plan.generate", status: "running" },
        { id: nodeRunId, node_key: "intro.generate_options", status: "running" },
      ],
    } as unknown as workflowApi.WorkflowDto);
    const getJob = vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(runningIntroJob);

    renderIntroPage();

    expect(await screen.findByRole("heading", { name: "任务正在处理" })).toBeVisible();
    expect(getJob).toHaveBeenCalledWith(jobId);
    expect(vi.mocked(useJobEvents)).toHaveBeenCalledWith(jobId, projectId);
  });

  it("对 pending exact 版本质量批准后创建唯一选择并在刷新后恢复", async () => {
    vi.mocked(workflowApi.getProjectWorkflow).mockResolvedValue({
      lessons: [],
      node_runs: [{ id: qualityNodeRunId, node_key: "intro.validate_options", status: "approved" }],
    } as unknown as workflowApi.WorkflowDto);
    vi.mocked(introOptionsApi.getLessonIntroOptions)
      .mockResolvedValueOnce(pendingOptions)
      .mockResolvedValueOnce(approvedOptions)
      .mockResolvedValue(selectedOptions);
    const quality = vi
      .spyOn(artifactsApi, "startArtifactVersionQualityValidation")
      .mockResolvedValue({
        events_url: `/api/v2/projects/${projectId}/events/stream`,
        node_run_id: qualityNodeRunId,
        status: "ready",
      });
    const approve = vi.spyOn(artifactsApi, "reviewArtifactVersion").mockResolvedValue({
      action: "approve",
      artifact_version_id: artifactVersionId,
      id: "01960000-0000-7000-8000-000000000211",
    } as artifactsApi.ApprovalDto);
    const select = vi
      .spyOn(introOptionsApi, "selectLessonIntroOption")
      .mockResolvedValue(selection);
    const user = userEvent.setup();
    const first = renderIntroPage();

    expect(await screen.findByRole("heading", { name: "科普倾向" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "应用倾向" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "故事倾向" })).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 4 })).toHaveLength(9);
    expect(screen.queryByText(recommendedOption.option_key)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "运行导入方案质量校验" }));
    await waitFor(() => expect(quality).toHaveBeenCalledOnce());
    expect(quality).toHaveBeenCalledWith(expect.objectContaining({ artifactVersionId }));
    expect(await screen.findByText("导入方案质量校验已通过，可以批准当前版本。")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "批准三类九套" }));
    await waitFor(() => expect(approve).toHaveBeenCalledOnce());
    expect(approve).toHaveBeenCalledWith(expect.objectContaining({ artifactVersionId }));

    await user.click(
      await screen.findByRole("button", { name: `选用方案：${recommendedOption.title}` }),
    );
    await waitFor(() => expect(select).toHaveBeenCalledOnce());
    expect(select).toHaveBeenCalledWith(
      expect.objectContaining({
        artifactVersionId,
        lessonId,
        optionKey: recommendedOption.option_key,
      }),
    );
    expect(await screen.findByText(`当前选择：${recommendedOption.title}`)).toBeVisible();

    first.unmount();
    renderIntroPage();
    expect(await screen.findByText(`当前选择：${recommendedOption.title}`)).toBeVisible();
    expect(
      screen.getByRole("button", { name: `已选方案：${recommendedOption.title}` }),
    ).toBeDisabled();
  });
});
