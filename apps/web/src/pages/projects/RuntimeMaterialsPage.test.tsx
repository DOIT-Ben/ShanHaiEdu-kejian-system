import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as artifactsApi from "@/features/artifacts/api/artifactsApi";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as materialsApi from "@/features/materials/api/materialsApi";
import * as workflowApi from "@/features/workflow/api/workflowApi";
import { RuntimeMaterialsPage } from "@/pages/projects/RuntimeMaterialsPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const materialId = "01960000-0000-7000-8000-000000000002";
const parseVersionId = "01960000-0000-7000-8000-000000000201";
const scopeArtifactId = "01960000-0000-7000-8000-000000000301";
const scopeVersionId = "01960000-0000-7000-8000-000000000302";
const nodeRunId = "01960000-0000-7000-8000-000000000401";
const jobId = "01960000-0000-7000-8000-000000000501";
const divisionArtifactId = "01960000-0000-7000-8000-000000000601";
const divisionVersionId = "01960000-0000-7000-8000-000000000602";
const divisionQualityNodeId = "01960000-0000-7000-8000-000000000603";
const material = {
  id: materialId,
  original_filename: "认识百分数.pdf",
  project_id: projectId,
  upload_status: "confirmed",
} as materialsApi.SourceMaterialDto;
const asset = {
  current_version: {
    byte_size: 4096,
    page_count: 8,
    scan_status: "clean",
    sha256: "a".repeat(64),
  },
  status: "active",
} as materialsApi.FileAssetDto;
const parseVersion = {
  id: parseVersionId,
  page_count: 8,
  parser_name: "pdf-parser",
  parser_version: "1.0",
  status: "succeeded",
  version_no: 1,
} as materialsApi.MaterialParseVersionDto;
const submittedScope = {
  artifact_type: "material_scope",
  current_approved_version: null,
  current_draft: null,
  current_submitted_version: {
    content: {
      material_parse_version_id: parseVersionId,
      page_end: 4,
      page_start: 2,
      source_material_id: materialId,
    },
    id: scopeVersionId,
    version_no: 1,
  },
  id: scopeArtifactId,
  project_id: projectId,
  status: "in_review",
} as unknown as artifactsApi.ArtifactDto;
const approvedScope = {
  ...submittedScope,
  current_approved_version: submittedScope.current_submitted_version,
  current_submitted_version: null,
  status: "approved",
} as artifactsApi.ArtifactDto;
const submittedDivision = {
  artifact_type: "lesson_division",
  current_approved_version: null,
  current_draft: null,
  current_submitted_version: {
    content: {
      lesson_count: 2,
      lesson_units: [
        {
          core_learning_outcome: "能用一一对应的方法数出 1 到 5。",
          duration_minutes: 40,
          lesson_unit_key: "lesson-1",
          material_scope: "教材第 2-3 页",
          position: 1,
          title: "数一数",
        },
        {
          core_learning_outcome: "能规范书写 1 到 5。",
          duration_minutes: 40,
          lesson_unit_key: "lesson-2",
          material_scope: "教材第 4 页",
          position: 2,
          title: "写一写",
        },
      ],
      scope_summary: "认识 1 到 5",
    },
    id: divisionVersionId,
    version_no: 1,
  },
  id: divisionArtifactId,
  project_id: projectId,
  status: "in_review",
} as unknown as artifactsApi.ArtifactDto;
const approvedDivision = {
  ...submittedDivision,
  current_approved_version: submittedDivision.current_submitted_version,
  current_submitted_version: null,
  status: "approved",
} as artifactsApi.ArtifactDto;
const queuedJob = {
  created_at: "2030-01-01T00:00:00Z",
  id: jobId,
  job_type: "workflow.node",
  lesson_unit_id: null,
  node_run_id: nodeRunId,
  progress_message: "正在生成课时划分",
  progress_percent: 35,
  project_id: projectId,
  status: "running",
  updated_at: "2030-01-01T00:00:01Z",
} as jobsApi.GenerationJobDto;

function renderMaterialsPage(selectedMaterialId: string | null = materialId) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  const path = selectedMaterialId
    ? `/app/projects/${projectId}/materials/${selectedMaterialId}`
    : `/app/projects/${projectId}/materials`;
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            element={<RuntimeMaterialsPage />}
            path="/app/projects/:projectId/materials/:materialId?"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeMaterialsPage", () => {
  beforeEach(() => {
    configureCsrfTokenProvider(() => "csrf-test-token");
    vi.spyOn(materialsApi, "listProjectMaterialsPage").mockResolvedValue({
      items: [material],
      nextCursor: null,
    });
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({ asset });
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockResolvedValue([parseVersion]);
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

  it("从项目教材列表恢复当前教材并读取成功解析", async () => {
    renderMaterialsPage(null);

    expect((await screen.findAllByText("8 页")).length).toBeGreaterThan(0);
    expect(materialsApi.listProjectMaterialsPage).toHaveBeenCalledWith({
      limit: 100,
      projectId,
    });
    expect(materialsApi.getSourceMaterialFileAsset).toHaveBeenCalledWith({
      materialId,
      projectId,
    });
  });

  it("提交并批准物理页范围后以 exact 版本启动课时划分任务", async () => {
    const listArtifacts = vi
      .mocked(artifactsApi.listProjectArtifactsPage)
      .mockResolvedValueOnce({ items: [], nextCursor: null })
      .mockResolvedValueOnce({ items: [approvedScope], nextCursor: null });
    const createScope = vi
      .spyOn(materialsApi, "createMaterialScopeVersion")
      .mockResolvedValue(submittedScope);
    const approveScope = vi.spyOn(artifactsApi, "reviewArtifactVersion").mockResolvedValue({
      action: "approve",
      artifact_version_id: scopeVersionId,
      id: "01960000-0000-7000-8000-000000000303",
    } as artifactsApi.ApprovalDto);
    const prepare = vi.spyOn(workflowApi, "prepareLessonDivision").mockResolvedValue({
      id: nodeRunId,
      node_key: "lesson.division.generate",
      status: "ready",
    });
    const start = vi.spyOn(workflowApi, "startNodeRun").mockResolvedValue({
      events_url: `/api/v2/generation-jobs/${jobId}/events/stream`,
      job_id: jobId,
      status: "queued",
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(queuedJob);
    const user = userEvent.setup();
    renderMaterialsPage();

    await user.clear(await screen.findByRole("spinbutton", { name: "起始物理页" }));
    await user.type(screen.getByRole("spinbutton", { name: "起始物理页" }), "2");
    await user.clear(screen.getByRole("spinbutton", { name: "结束物理页" }));
    await user.type(screen.getByRole("spinbutton", { name: "结束物理页" }), "4");
    await user.click(screen.getByRole("button", { name: "提交教材范围" }));

    await waitFor(() => expect(createScope).toHaveBeenCalledOnce());
    expect(createScope.mock.calls[0]?.[0]).toMatchObject({
      input: {
        material_parse_version_id: parseVersionId,
        page_end: 4,
        page_start: 2,
        source_material_id: materialId,
      },
      projectId,
    });
    expect(typeof createScope.mock.calls[0]?.[0].idempotencyKey).toBe("string");

    await user.click(await screen.findByRole("button", { name: "批准教材范围" }));
    await waitFor(() => expect(approveScope).toHaveBeenCalledOnce());
    expect(approveScope.mock.calls[0]?.[0]).toMatchObject({
      artifactVersionId: scopeVersionId,
      input: { action: "approve" },
    });
    await waitFor(() => expect(listArtifacts).toHaveBeenCalledTimes(2));

    await user.click(await screen.findByRole("button", { name: "生成课时划分" }));
    await waitFor(() => expect(start).toHaveBeenCalledOnce());
    expect(prepare.mock.calls[0]?.[0]).toMatchObject({
      materialScopeArtifactVersionId: scopeVersionId,
      projectId,
    });
    expect(start.mock.calls[0]?.[0]).toMatchObject({ nodeRunId });
    expect(await screen.findByRole("heading", { name: "任务正在处理" })).toBeVisible();
    expect(vi.mocked(useJobEvents)).toHaveBeenCalledWith(jobId, projectId);
  });

  it("刷新后从正式列表恢复已批准范围与课时划分终态", async () => {
    const succeededJob = {
      ...queuedJob,
      progress_message: "课时划分已生成",
      progress_percent: 100,
      result_artifact_version_id: "01960000-0000-7000-8000-000000000601",
      status: "succeeded",
    } as jobsApi.GenerationJobDto;
    vi.mocked(artifactsApi.listProjectArtifactsPage).mockResolvedValue({
      items: [approvedScope],
      nextCursor: null,
    });
    vi.mocked(jobsApi.listProjectGenerationJobsPage).mockResolvedValue({
      items: [succeededJob],
      nextCursor: null,
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(succeededJob);
    const prepare = vi.spyOn(workflowApi, "prepareLessonDivision");
    const start = vi.spyOn(workflowApi, "startNodeRun");

    renderMaterialsPage();

    expect(await screen.findByText("已批准教材范围：第 2-4 页")).toBeVisible();
    expect(await screen.findByRole("heading", { name: "任务已经完成" })).toBeVisible();
    expect(prepare).not.toHaveBeenCalled();
    expect(start).not.toHaveBeenCalled();
    expect(vi.mocked(useJobEvents)).not.toHaveBeenCalledWith(jobId, projectId);
  });

  it("展示生成课时并按 exact 版本完成质量校验与批准", async () => {
    const succeededJob = {
      ...queuedJob,
      progress_message: "课时划分已生成",
      progress_percent: 100,
      result_artifact_version_id: divisionVersionId,
      status: "succeeded",
    } as jobsApi.GenerationJobDto;
    const listArtifacts = vi
      .mocked(artifactsApi.listProjectArtifactsPage)
      .mockResolvedValueOnce({
        items: [submittedDivision, approvedScope],
        nextCursor: null,
      })
      .mockResolvedValueOnce({
        items: [approvedDivision, approvedScope],
        nextCursor: null,
      });
    vi.mocked(jobsApi.listProjectGenerationJobsPage).mockResolvedValue({
      items: [succeededJob],
      nextCursor: null,
    });
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(succeededJob);
    vi.mocked(workflowApi.getProjectWorkflow).mockResolvedValue({
      lessons: [],
      node_runs: [
        {
          id: divisionQualityNodeId,
          node_key: "lesson.division.validate",
          status: "approved",
        },
      ],
    } as unknown as workflowApi.WorkflowDto);
    const startQuality = vi
      .spyOn(artifactsApi, "startArtifactVersionQualityValidation")
      .mockResolvedValue({
        events_url: `/api/v2/projects/${projectId}/events/stream`,
        node_run_id: divisionQualityNodeId,
        status: "ready",
      });
    const approveDivision = vi.spyOn(artifactsApi, "reviewArtifactVersion").mockResolvedValue({
      action: "approve",
      artifact_version_id: divisionVersionId,
      id: "01960000-0000-7000-8000-000000000604",
    } as artifactsApi.ApprovalDto);
    const user = userEvent.setup();

    renderMaterialsPage();

    expect(await screen.findByRole("heading", { name: "第 1 课时 · 数一数" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "第 2 课时 · 写一写" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "运行课时划分质量校验" }));
    await waitFor(() => expect(startQuality).toHaveBeenCalledOnce());
    expect(startQuality.mock.calls[0]?.[0]).toMatchObject({
      artifactVersionId: divisionVersionId,
    });
    expect(await screen.findByText("课时划分质量校验已通过，可以批准当前版本。")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "批准课时划分" }));
    await waitFor(() => expect(approveDivision).toHaveBeenCalledOnce());
    expect(approveDivision.mock.calls[0]?.[0]).toMatchObject({
      artifactVersionId: divisionVersionId,
      input: { action: "approve" },
    });
    await waitFor(() => expect(listArtifacts).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("link", { name: "查看已建立课时" })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/lessons`,
    );
  });

  it("教材文件读取失败时保留解析记录", async () => {
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockRejectedValue(
      new TypeError("file unavailable"),
    );
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockResolvedValue([parseVersion]);
    renderMaterialsPage();

    expect(await screen.findByRole("heading", { name: "第 1 次解析" })).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("教材文件暂时无法读取");
  });

  it("解析记录读取失败时保留教材文件", async () => {
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({ asset });
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockRejectedValue(
      new TypeError("parse unavailable"),
    );
    renderMaterialsPage();

    expect(await screen.findByText("8 页")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("解析记录暂时无法读取");
  });
});
