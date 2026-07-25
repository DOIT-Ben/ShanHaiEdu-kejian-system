import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as artifactsApi from "@/features/artifacts/api/artifactsApi";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import * as workflowApi from "@/features/workflow/api/workflowApi";
import { RuntimeLessonWorkbenchPage } from "@/pages/projects/RuntimeLessonWorkbenchPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";
import { useProjectEvents } from "@/shared/api/useProjectEvents";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const lessonId = "01960000-0000-7000-8000-000000000002";
const otherProjectId = "01960000-0000-7000-8000-000000000099";
const otherLessonId = "01960000-0000-7000-8000-000000000098";
const nodeRunId = "01960000-0000-7000-8000-000000000101";
const jobId = "01960000-0000-7000-8000-000000000102";
const artifactId = "01960000-0000-7000-8000-000000000103";
const generatedVersionId = "01960000-0000-7000-8000-000000000104";
const submittedVersionId = "01960000-0000-7000-8000-000000000105";
const qualityNodeRunId = "01960000-0000-7000-8000-000000000107";
const contentDefinitionVersionId = "01960000-0000-7000-8000-000000000109";
const teacherId = "01960000-0000-7000-8000-000000000110";

const lessonPlanContent = {
  teaching_content: { lesson_topic: "百分数的意义", duration_minutes: 40 },
  material_analysis: { current_focus: "理解百分数表示两个数量之间的关系。" },
  learner_analysis: { likely_learning_difficulties: ["混淆百分数与具体数量"] },
  design_intent: { teaching_main_line: "情境比较、图示表达、概括意义。" },
  teaching_objectives: [{ observable_outcome: "能解释一个百分数的实际含义。" }],
  key_difficulties_and_strategies: { key_learning_focus: "百分数的意义" },
  preparation: { teacher_resources: ["百格图"] },
  teaching_process: [{ process_title: "在比较中认识百分数" }],
  board_design: { board_layout: "数量关系与百分数表达" },
  lesson_summary: { teacher_closure: "百分数表示一个数是另一个数的百分之几。" },
  differentiated_homework: [{ homework_task: "解释生活中的一个百分数。" }],
  teaching_reflection: { reflection_state: "not_taught", teacher_reflection_record: "" },
};

const generatedVersion = {
  content: lessonPlanContent,
  content_hash: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  context_snapshot_id: null,
  created_at: "2030-01-01T00:00:00Z",
  created_by: teacherId,
  id: generatedVersionId,
  prompt_snapshot_id: null,
  render_summary: {},
  source_kind: "model",
  source_node_run_id: nodeRunId,
  validation_report: {},
  version_no: 1,
} satisfies artifactsApi.ArtifactVersionDto;
const submittedVersion = {
  ...generatedVersion,
  content: {
    ...lessonPlanContent,
    teaching_content: { ...lessonPlanContent.teaching_content, lesson_topic: "百分数初步认识" },
  },
  id: submittedVersionId,
  source_kind: "manual",
  source_node_run_id: null,
  version_no: 2,
} satisfies artifactsApi.ArtifactVersionDto;
const draftArtifact = {
  artifact_key: "lesson-plan/main",
  artifact_type: "lesson_plan",
  branch_key: "lesson_plan",
  content_definition_version_id: contentDefinitionVersionId,
  created_at: "2030-01-01T00:00:00Z",
  current_approved_version: null,
  current_draft: {
    autosaved_at: "2030-01-01T00:00:00Z",
    based_on_version_id: generatedVersionId,
    content: lessonPlanContent,
    draft_branch: "main",
    id: "01960000-0000-7000-8000-000000000106",
    lock_version: 1,
    validation_report: {},
  },
  current_submitted_version: generatedVersion,
  id: artifactId,
  lesson_unit_id: lessonId,
  lock_version: 1,
  project_id: projectId,
  stale_reason: null,
  status: "in_review",
  updated_at: "2030-01-01T00:00:01Z",
} satisfies artifactsApi.ArtifactDto;
const submittedArtifact = {
  ...draftArtifact,
  current_draft: {
    ...draftArtifact.current_draft,
    based_on_version_id: submittedVersionId,
    content: submittedVersion.content,
    lock_version: 2,
  },
  current_submitted_version: submittedVersion,
  lock_version: 2,
} satisfies artifactsApi.ArtifactDto;
const approvedArtifact = {
  ...submittedArtifact,
  current_approved_version: submittedVersion,
  current_submitted_version: null,
  lock_version: 3,
  status: "approved",
} satisfies artifactsApi.ArtifactDto;
const succeededJob = {
  created_at: "2030-01-01T00:00:00Z",
  id: jobId,
  job_type: "workflow.node",
  lesson_unit_id: lessonId,
  node_run_id: nodeRunId,
  progress_message: "十二部分教案已生成",
  progress_percent: 100,
  project_id: projectId,
  result_artifact_version_id: generatedVersionId,
  status: "succeeded",
  updated_at: "2030-01-01T00:00:01Z",
} as jobsApi.GenerationJobDto;

function renderPage(stepKey = "lesson_plan") {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[`/app/projects/${projectId}/lessons/${lessonId}/work/${stepKey}`]}
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

describe("RuntimeLessonWorkbenchPage", () => {
  beforeEach(() => {
    configureCsrfTokenProvider(() => "csrf-test-token");
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      id: projectId,
      title: "认识百分数",
    } as Awaited<ReturnType<typeof projectsApi.getProject>>);
    vi.spyOn(lessonsApi, "getLesson").mockResolvedValue({
      lesson: {
        id: lessonId,
        project_id: projectId,
        lesson_key: "lesson-1",
        title: "百分数的意义",
        objective_summary: "理解百分数表示一个数是另一个数的百分之几。",
        scope_summary: "认识百分数并能正确读写。",
        estimated_minutes: 40,
        branches: [
          {
            branch_key: "lesson_plan",
            enabled: true,
            settings: {},
            workflow_status: "not_ready",
          },
          {
            branch_key: "ppt",
            enabled: true,
            settings: {},
            workflow_status: "not_ready",
          },
        ],
      },
    } as Awaited<ReturnType<typeof lessonsApi.getLesson>>);
    vi.spyOn(artifactsApi, "listProjectArtifactsPage").mockResolvedValue({
      items: [],
      nextCursor: null,
    });
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

  it("只渲染可归属当前课时的事实并从正式接口读取制作状态", async () => {
    renderPage();

    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("百分数的意义");
    expect(await screen.findByRole("button", { name: "生成十二部分教案" })).toBeEnabled();
    expect(artifactsApi.listProjectArtifactsPage).toHaveBeenCalledWith({
      artifactType: "lesson_plan",
      lessonId,
      limit: 100,
      projectId,
    });
    expect(screen.getByRole("link", { name: /返回项目/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}`,
    );
    expect(screen.getByRole("link", { name: /课堂 PPT/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons/${lessonId}/work/ppt`,
    );
  });

  it("以 exact lesson 准备并启动异步教案 Job", async () => {
    const prepare = vi.spyOn(workflowApi, "prepareLessonPlanGeneration").mockResolvedValue({
      id: nodeRunId,
      node_key: "lesson_plan.generate",
      status: "ready",
    });
    const start = vi.spyOn(workflowApi, "startNodeRun").mockResolvedValue({
      events_url: `/api/v2/generation-jobs/${jobId}/events/stream`,
      job_id: jobId,
      status: "queued",
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue({
      ...succeededJob,
      progress_message: "正在生成十二部分教案",
      progress_percent: 35,
      result_artifact_version_id: null,
      status: "running",
    });
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByLabelText("本次生成要求"), "增加一个课堂辨析活动");
    await user.click(screen.getByRole("button", { name: "生成十二部分教案" }));

    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(prepare.mock.calls[0]?.[0]).toMatchObject({ lessonId });
    expect(start.mock.calls[0]?.[0]).toMatchObject({
      nodeRunId,
      userRevision: "增加一个课堂辨析活动",
    });
    expect(await screen.findByRole("heading", { name: "任务正在处理" })).toBeVisible();
    expect(vi.mocked(useJobEvents)).toHaveBeenCalledWith(jobId, projectId);
  });

  it("刷新后恢复 exact 教案并按 ETag 保存、提交、质量校验和批准", async () => {
    vi.mocked(artifactsApi.listProjectArtifactsPage).mockResolvedValue({
      items: [
        {
          ...draftArtifact,
          id: "01960000-0000-7000-8000-000000000199",
          lesson_unit_id: otherLessonId,
        },
        draftArtifact,
      ],
      nextCursor: null,
    });
    const getArtifact = vi
      .spyOn(artifactsApi, "getArtifact")
      .mockResolvedValueOnce({ artifact: draftArtifact, etag: 'W/"1"' })
      .mockResolvedValueOnce({ artifact: submittedArtifact, etag: 'W/"2"' })
      .mockResolvedValueOnce({ artifact: approvedArtifact, etag: 'W/"2"' });
    vi.mocked(jobsApi.listProjectGenerationJobsPage).mockResolvedValue({
      items: [succeededJob],
      nextCursor: null,
    });
    vi.mocked(workflowApi.getProjectWorkflow).mockResolvedValue({
      lessons: [],
      node_runs: [
        { id: nodeRunId, node_key: "lesson_plan.generate", status: "review_required" },
        { id: qualityNodeRunId, node_key: "lesson_plan.validate", status: "approved" },
      ],
    } as unknown as workflowApi.WorkflowDto);
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(succeededJob);
    const submittedDraft = submittedArtifact.current_draft;
    const save = vi.spyOn(artifactsApi, "saveArtifactDraft").mockResolvedValue({
      draft: submittedDraft,
      etag: 'W/"2"',
    });
    const submit = vi
      .spyOn(artifactsApi, "submitArtifactVersion")
      .mockResolvedValue(submittedVersion);
    const quality = vi
      .spyOn(artifactsApi, "startArtifactVersionQualityValidation")
      .mockResolvedValue({
        events_url: `/api/v2/projects/${projectId}/events/stream`,
        node_run_id: qualityNodeRunId,
        status: "ready",
      });
    const approve = vi.spyOn(artifactsApi, "reviewArtifactVersion").mockResolvedValue({
      action: "approve",
      artifact_version_id: submittedVersionId,
      id: "01960000-0000-7000-8000-000000000108",
    } as artifactsApi.ApprovalDto);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("heading", { name: "一、教学内容" })).toBeVisible();
    expect(screen.getAllByRole("heading", { name: "十二、教学反思" })).toHaveLength(2);
    const topic = screen.getByRole("textbox", { name: "课题" });
    await user.clear(topic);
    await user.type(topic, "百分数初步认识");
    await user.click(screen.getByRole("button", { name: "保存草稿" }));

    await waitFor(() => expect(save).toHaveBeenCalledOnce());
    expect(save.mock.calls[0]?.[0]).toMatchObject({
      artifactId,
      draftBranch: "main",
      etag: 'W/"1"',
      input: {
        content: {
          teaching_content: { lesson_topic: "百分数初步认识" },
        },
      },
    });
    await user.click(screen.getByRole("button", { name: "提交当前草稿" }));
    await waitFor(() => expect(submit).toHaveBeenCalledOnce());
    expect(submit.mock.calls[0]?.[0]).toMatchObject({
      artifactId,
      draftBranch: "main",
      etag: 'W/"2"',
    });
    await waitFor(() => expect(getArtifact).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("当前待确认版本：2")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "运行教案质量校验" }));
    await waitFor(() => expect(quality).toHaveBeenCalledOnce());
    expect(quality.mock.calls[0]?.[0]).toMatchObject({ artifactVersionId: submittedVersionId });
    expect(await screen.findByText("教案质量校验已通过，可以批准当前版本。")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "批准当前版本" }));
    await waitFor(() => expect(approve).toHaveBeenCalledOnce());
    expect(approve.mock.calls[0]?.[0]).toMatchObject({ artifactVersionId: submittedVersionId });
    expect(await screen.findByRole("link", { name: "进入课堂导入" })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons/${lessonId}/work/intro_options`,
    );
  });

  it("旧连字符路由与未知步骤都不会泄漏内部键", async () => {
    const first = renderPage("lesson-plan");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("教案");
    expect(screen.queryByText(/lesson-plan/)).not.toBeInTheDocument();
    first.unmount();

    renderPage("future-node-v2");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("当前步骤");
    expect(screen.queryByText(/future-node-v2/)).not.toBeInTheDocument();
  });

  it("拒绝打开不属于路由项目的课时且不启动项目事件流", async () => {
    vi.mocked(lessonsApi.getLesson).mockResolvedValueOnce({
      lesson: {
        branches: [],
        created_at: "2030-01-01T00:00:00Z",
        estimated_minutes: 40,
        id: lessonId,
        lesson_key: "lesson-1",
        lock_version: 1,
        objective_summary: "不应展示",
        position: 1,
        project_id: otherProjectId,
        scope_summary: "不应展示",
        source_division_version_id: "01960000-0000-7000-8000-000000000098",
        status: "active",
        title: "其他项目课时",
        updated_at: "2030-01-01T00:00:01Z",
      },
    });

    renderPage();

    expect(await screen.findByRole("heading", { name: "暂时无法打开课时" })).toBeVisible();
    expect(screen.queryByText("其他项目课时")).not.toBeInTheDocument();
    expect(vi.mocked(useProjectEvents)).not.toHaveBeenCalledWith(projectId);
  });
});
