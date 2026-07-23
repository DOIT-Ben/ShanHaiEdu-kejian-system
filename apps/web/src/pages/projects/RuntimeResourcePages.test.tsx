import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as artifactsApi from "@/features/artifacts/api/artifactsApi";
import * as assetsApi from "@/features/assets/api/assetsApi";
import * as jobsApi from "@/features/jobs/api/jobsApi";
import * as lessonsApi from "@/features/lessons/api/lessonsApi";
import * as materialsApi from "@/features/materials/api/materialsApi";
import * as automationPolicyApi from "@/features/projects/api/automationPolicyApi";
import * as projectsApi from "@/features/projects/api/projectsApi";
import { RuntimeArtifactPage } from "@/pages/projects/RuntimeArtifactPage";
import { RuntimeAssetsPage } from "@/pages/projects/RuntimeAssetsPage";
import { RuntimeJobPage } from "@/pages/projects/RuntimeJobPage";
import { RuntimeLessonsPage } from "@/pages/projects/RuntimeLessonsPage";
import { RuntimeMaterialsPage } from "@/pages/projects/RuntimeMaterialsPage";
import { RuntimeProjectOverviewPage } from "@/pages/projects/RuntimeProjectOverviewPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";
import { useJobEvents } from "@/shared/api/useJobEvents";
import { useProjectEvents } from "@/shared/api/useProjectEvents";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/shared/api/useJobEvents", () => ({ useJobEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const materialId = "01960000-0000-7000-8000-000000000002";
const lessonId = "01960000-0000-7000-8000-000000000003";
const jobId = "01960000-0000-7000-8000-000000000004";
const artifactId = "01960000-0000-7000-8000-000000000005";
const otherProjectId = "01960000-0000-7000-8000-000000000099";

function renderRoute(path: string, routePath: string, element: React.ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={element} path={routePath} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Runtime resource pages", () => {
  beforeEach(() => configureCsrfTokenProvider(() => "csrf-test-token"));

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("uses the material deep link to reconcile the file asset and parse versions", async () => {
    const getFileAsset = vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({
      asset: {
        asset_key: "教材.pdf",
        current_version: {
          byte_size: 4096,
          page_count: 8,
          scan_status: "clean",
          sha256: "a".repeat(64),
        },
        status: "active",
      } as materialsApi.FileAssetDto,
    });
    const listParseVersions = vi
      .spyOn(materialsApi, "listMaterialParseVersions")
      .mockResolvedValue([
        {
          id: "01960000-0000-7000-8000-000000000201",
          parser_name: "pdf-parser",
          parser_version: "1.0",
          status: "succeeded",
          version_no: 1,
        } as materialsApi.MaterialParseVersionDto,
      ]);

    renderRoute(
      `/app/projects/${projectId}/materials/${materialId}`,
      "/app/projects/:projectId/materials/:materialId",
      <RuntimeMaterialsPage />,
    );

    expect(await screen.findByText("8 页")).toBeVisible();
    expect(getFileAsset).toHaveBeenCalledWith({ materialId, projectId });
    expect(listParseVersions).toHaveBeenCalledWith({ materialId, projectId });
  });

  it("shows an explicit contract block when the project has no lessons", async () => {
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      grade: "六年级",
      id: projectId,
      knowledge_point: "百分数的意义",
      title: "认识百分数",
    } as projectsApi.ProjectDto);
    vi.spyOn(automationPolicyApi, "getProjectAutomationPolicyVersioned").mockResolvedValue({
      etag: '"policy-v1"',
      policy: { mode: "guided" } as automationPolicyApi.AutomationPolicyDto,
    });
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v0"',
      lessons: [],
      lockVersion: 0,
    });

    renderRoute(
      `/app/projects/${projectId}`,
      "/app/projects/:projectId",
      <RuntimeProjectOverviewPage />,
    );

    expect(
      await screen.findByText("当前项目还没有课时。课时创建和教案生成暂不可用。"),
    ).toBeVisible();
    expect(screen.queryByText("课时建议还没有准备好。")).not.toBeInTheDocument();
  });

  it("keeps failed lesson and policy reads distinct from an empty project", async () => {
    vi.spyOn(projectsApi, "getProject").mockResolvedValue({
      grade: "六年级",
      id: projectId,
      knowledge_point: "百分数的意义",
      title: "认识百分数",
    } as projectsApi.ProjectDto);
    vi.spyOn(automationPolicyApi, "getProjectAutomationPolicyVersioned").mockRejectedValue(
      new Error("policy unavailable"),
    );
    const listLessons = vi
      .spyOn(lessonsApi, "listProjectLessons")
      .mockRejectedValueOnce(new Error("lessons unavailable"))
      .mockResolvedValue({ etag: '"lessons-v0"', lessons: [], lockVersion: 0 });

    renderRoute(
      `/app/projects/${projectId}`,
      "/app/projects/:projectId",
      <RuntimeProjectOverviewPage />,
    );

    expect(await screen.findByText("课时暂时无法读取，请检查网络后重试。")).toBeVisible();
    expect(screen.getByText("制作方式暂时无法读取，请检查网络后重试。")).toBeVisible();
    expect(
      screen.queryByText("当前项目还没有课时。课时创建和教案生成暂不可用。"),
    ).not.toBeInTheDocument();

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "重新读取课时" }));
    expect(
      await screen.findByText("当前项目还没有课时。课时创建和教案生成暂不可用。"),
    ).toBeVisible();
    expect(listLessons).toHaveBeenCalledTimes(2);
  });

  it("saves a lesson collection with the current ETag and a new idempotency key", async () => {
    const lesson = {
      branches: [
        { branch_key: "lesson_plan", enabled: true, settings: {}, workflow_status: "not_ready" },
      ],
      estimated_minutes: 40,
      id: lessonId,
      objective_summary: "理解百分数的意义",
      position: 1,
      scope_summary: "认识百分数",
      title: "百分数的意义",
    } as lessonsApi.LessonDto;
    vi.spyOn(lessonsApi, "listProjectLessons").mockResolvedValue({
      etag: '"lessons-v3"',
      lessons: [lesson],
      lockVersion: 3,
    });
    const updateCollection = vi
      .spyOn(lessonsApi, "updateProjectLessons")
      .mockResolvedValue({ etag: '"lessons-v4"', lessons: [lesson], lockVersion: 4 });

    renderRoute(
      `/app/projects/${projectId}/lessons`,
      "/app/projects/:projectId/lessons",
      <RuntimeLessonsPage />,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "保存课时集合" }));

    await waitFor(() => expect(updateCollection).toHaveBeenCalledOnce());
    const collectionRequest = updateCollection.mock.calls[0]?.[0];
    expect(collectionRequest?.etag).toBe('"lessons-v3"');
    expect(collectionRequest?.projectId).toBe(projectId);
    expect(typeof collectionRequest?.idempotencyKey).toBe("string");
  });

  it("reads and cancels the same generation job represented by the route", async () => {
    const job = {
      created_at: "2030-01-01T00:00:00Z",
      id: jobId,
      job_type: "parse_material",
      progress_message: "正在整理教材",
      progress_percent: 35,
      project_id: projectId,
      status: "running",
      updated_at: "2030-01-01T00:00:01Z",
    } as jobsApi.GenerationJobDto;
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(job);
    const cancelJob = vi
      .spyOn(jobsApi, "cancelGenerationJob")
      .mockResolvedValue({ ...job, status: "cancel_requested" });

    renderRoute(
      `/app/projects/${projectId}/jobs/${jobId}`,
      "/app/projects/:projectId/jobs/:jobId",
      <RuntimeJobPage />,
    );

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "取消任务" }));

    await waitFor(() => expect(cancelJob).toHaveBeenCalledOnce());
    const cancelRequest = cancelJob.mock.calls[0]?.[0];
    expect(cancelRequest?.jobId).toBe(jobId);
    expect(typeof cancelRequest?.idempotencyKey).toBe("string");
  });

  it("blocks a generation job that does not belong to the route project", async () => {
    const job = {
      created_at: "2030-01-01T00:00:00Z",
      id: jobId,
      job_type: "parse_material",
      progress_message: "正在整理教材",
      progress_percent: 35,
      project_id: otherProjectId,
      status: "running",
      updated_at: "2030-01-01T00:00:01Z",
    } as jobsApi.GenerationJobDto;
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue(job);
    const cancelJob = vi.spyOn(jobsApi, "cancelGenerationJob");

    renderRoute(
      `/app/projects/${projectId}/jobs/${jobId}`,
      "/app/projects/:projectId/jobs/:jobId",
      <RuntimeJobPage />,
    );

    expect(await screen.findByRole("heading", { name: "任务暂时无法打开" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "取消任务" })).not.toBeInTheDocument();
    expect(cancelJob).not.toHaveBeenCalled();
    expect(vi.mocked(useJobEvents)).not.toHaveBeenCalledWith(jobId, projectId);
  });

  it("does not keep the job event stream open after a terminal status is loaded", async () => {
    vi.spyOn(jobsApi, "getGenerationJob").mockResolvedValue({
      created_at: "2030-01-01T00:00:00Z",
      id: jobId,
      job_type: "parse_material",
      progress_message: "教材整理完成",
      progress_percent: 100,
      project_id: projectId,
      status: "succeeded",
      updated_at: "2030-01-01T00:00:01Z",
    });

    renderRoute(
      `/app/projects/${projectId}/jobs/${jobId}`,
      "/app/projects/:projectId/jobs/:jobId",
      <RuntimeJobPage />,
    );

    expect(await screen.findByRole("heading", { name: "任务已经完成" })).toBeVisible();
    expect(vi.mocked(useJobEvents)).not.toHaveBeenCalledWith(jobId, projectId);
  });

  it("blocks artifact writes when the runtime cannot safely display review content", async () => {
    const artifact = {
      artifact_type: "lesson_plan",
      content_definition_version_id: "content-definition-version-1",
      current_approved_version: null,
      current_draft: { draft_branch: "main" },
      current_submitted_version: { id: "version-1", version_no: 1 },
      id: artifactId,
      project_id: projectId,
      status: "in_review",
    } as artifactsApi.ArtifactDto;
    vi.spyOn(artifactsApi, "getArtifact").mockResolvedValue({
      artifact,
      etag: '"artifact-v2"',
    });
    const submit = vi.spyOn(artifactsApi, "submitArtifactVersion");
    const approve = vi.spyOn(artifactsApi, "reviewArtifactVersion");

    renderRoute(
      `/app/projects/${projectId}/artifacts/${artifactId}`,
      "/app/projects/:projectId/artifacts/:artifactId",
      <RuntimeArtifactPage />,
    );

    expect(await screen.findByText(/当前只显示版本状态，正文查看与审核暂不可用/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "保存草稿" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "提交当前草稿" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "批准当前版本" })).not.toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
    expect(approve).not.toHaveBeenCalled();
  });

  it("blocks an artifact that does not belong to the route project", async () => {
    const artifact = {
      artifact_type: "lesson_plan",
      current_approved_version: null,
      current_draft: { draft_branch: "main" },
      current_submitted_version: { id: "version-1", version_no: 1 },
      id: artifactId,
      project_id: otherProjectId,
      status: "in_review",
    } as artifactsApi.ArtifactDto;
    vi.spyOn(artifactsApi, "getArtifact").mockResolvedValue({
      artifact,
      etag: '"artifact-v2"',
    });
    const submit = vi.spyOn(artifactsApi, "submitArtifactVersion");
    const approve = vi.spyOn(artifactsApi, "reviewArtifactVersion");

    renderRoute(
      `/app/projects/${projectId}/artifacts/${artifactId}`,
      "/app/projects/:projectId/artifacts/:artifactId",
      <RuntimeArtifactPage />,
    );

    expect(await screen.findByRole("heading", { name: "内容版本暂时无法打开" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "提交当前草稿" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "批准当前版本" })).not.toBeInTheDocument();
    expect(submit).not.toHaveBeenCalled();
    expect(approve).not.toHaveBeenCalled();
    expect(vi.mocked(useProjectEvents)).not.toHaveBeenCalledWith(projectId);
  });

  it("reads both asset views and binds or removes only a selected server asset", async () => {
    const slot = {
      active_bindings: [{ id: "binding-1", file_asset_version_id: "existing-version" }],
      asset_type: "image",
      cardinality: "one",
      id: "slot-1",
      required: true,
      status: "satisfied",
      target_contract: { allowed_mime_types: ["image/png"], require_clean_scan: true },
    } as assetsApi.ProjectAssetSlotDto;
    const listSlots = vi.spyOn(assetsApi, "listProjectAssetSlots").mockResolvedValue({
      items: [slot],
    });
    const getPackage = vi.spyOn(assetsApi, "getProjectAssetPackage").mockResolvedValue({
      items: [slot],
      projectId,
    });
    const bind = vi
      .spyOn(assetsApi, "bindProjectAsset")
      .mockResolvedValue({ id: "binding-2" } as assetsApi.AssetBindingDto);
    const unbind = vi
      .spyOn(assetsApi, "unbindProjectAsset")
      .mockResolvedValue({ id: "binding-1", is_active: false } as assetsApi.AssetBindingDto);

    renderRoute(
      `/app/projects/${projectId}/assets?fileVersionId=selected-version&assetLabel=${encodeURIComponent("课堂封面")}`,
      "/app/projects/:projectId/assets",
      <RuntimeAssetsPage />,
    );

    expect(await screen.findByText("素材包包含 1 个素材位置。")).toBeVisible();
    expect(listSlots).toHaveBeenCalledWith({ projectId });
    expect(getPackage).toHaveBeenCalledWith({ projectId });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "放入图片位置 1" }));
    await waitFor(() => expect(bind).toHaveBeenCalledOnce());
    const bindRequest = bind.mock.calls[0]?.[0];
    expect(bindRequest?.slotId).toBe("slot-1");
    expect(bindRequest?.input.file_asset_version_id).toBe("selected-version");
    expect(typeof bindRequest?.idempotencyKey).toBe("string");

    await user.click(screen.getByRole("button", { name: "移除图片素材 1" }));
    await waitFor(() => expect(unbind).toHaveBeenCalledOnce());
    const unbindRequest = unbind.mock.calls[0]?.[0];
    expect(unbindRequest?.bindingId).toBe("binding-1");
    expect(typeof unbindRequest?.idempotencyKey).toBe("string");
  });
});
