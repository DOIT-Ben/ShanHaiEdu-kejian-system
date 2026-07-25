import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as materialsApi from "@/features/materials/api/materialsApi";
import { RuntimeMaterialsPage } from "@/pages/projects/RuntimeMaterialsPage";

const workflow = vi.hoisted(() => ({
  approvedVersionId: undefined as string | undefined,
  scopeMaterialId: undefined as string | undefined,
  scopeParseVersionId: undefined as string | undefined,
}));

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/features/materials/components/MaterialDetailsPanel", () => ({
  MaterialDetailsPanel: () => <div>教材详情</div>,
}));
vi.mock("@/features/materials/components/MaterialScopePanel", () => ({
  MaterialScopePanel: ({ pages }: { pages: unknown[] }) => <div>范围页数 {pages.length}</div>,
}));
vi.mock("@/features/lessons/components/LessonDivisionWorkflowPanel", () => ({
  LessonDivisionWorkflowPanel: ({
    materialScopeVersionId,
  }: {
    materialScopeVersionId?: string;
  }) => <div>课时划分范围 {materialScopeVersionId ?? "未批准"}</div>,
}));
vi.mock("@/features/materials/hooks/useMaterialScopeWorkflow", () => ({
  useMaterialScopeRuntime: () => ({
    aggregateQuery: { refetch: vi.fn() },
    artifact: workflow.approvedVersionId
      ? {
          current_approved_version: {
            content: {
              material_parse_version_id: workflow.scopeParseVersionId,
              source_material_id: workflow.scopeMaterialId,
            },
            id: workflow.approvedVersionId,
          },
          status: "approved",
        }
      : undefined,
    latestApproval: workflow.approvedVersionId
      ? { action: "approve", artifact_version_id: workflow.approvedVersionId }
      : undefined,
    refetch: vi.fn(),
  }),
}));

const projectId = "01960000-0000-7000-8000-000000000001";
const materialId = "01960000-0000-7000-8000-000000000002";
const parseVersionId = "01960000-0000-7000-8000-000000000003";

function renderPage(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<RuntimeMaterialsPage />} path="/app/projects/:projectId/materials" />
          <Route
            element={<RuntimeMaterialsPage />}
            path="/app/projects/:projectId/materials/:materialId"
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeMaterialsPage workflow", () => {
  beforeEach(() => {
    workflow.approvedVersionId = undefined;
    workflow.scopeMaterialId = undefined;
    workflow.scopeParseVersionId = undefined;
    vi.spyOn(materialsApi, "listProjectTextbookMaterials").mockResolvedValue([]);
  });

  afterEach(() => vi.restoreAllMocks());

  it("discovers project textbooks without a material deep link", async () => {
    vi.mocked(materialsApi.listProjectTextbookMaterials).mockResolvedValue([
      {
        id: materialId,
        original_filename: "一年级数学教材.pdf",
        upload_status: "confirmed",
      } as materialsApi.SourceMaterialDto,
    ]);

    renderPage(`/app/projects/${projectId}/materials`);

    expect(await screen.findByRole("link", { name: /一年级数学教材/ })).toHaveAttribute(
      "href",
      `/app/projects/${projectId}/materials/${materialId}`,
    );
    expect(materialsApi.listProjectTextbookMaterials).toHaveBeenCalledWith(projectId);
    expect(screen.getByLabelText("选择教材 PDF")).toBeVisible();
  });

  it("binds exact parse pages and only exposes an approved scope to division", async () => {
    workflow.approvedVersionId = "scope-version-1";
    workflow.scopeMaterialId = materialId;
    workflow.scopeParseVersionId = parseVersionId;
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({
      asset: { status: "active" } as materialsApi.FileAssetDto,
    });
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockResolvedValue([
      {
        id: parseVersionId,
        page_count: 2,
        status: "succeeded",
      } as materialsApi.MaterialParseVersionDto,
    ]);
    const listPages = vi
      .spyOn(materialsApi, "listMaterialParsePages")
      .mockResolvedValue([
        { page_number: 1 } as materialsApi.MaterialParsePageDto,
        { page_number: 2 } as materialsApi.MaterialParsePageDto,
      ]);

    renderPage(`/app/projects/${projectId}/materials/${materialId}`);

    expect(await screen.findByText("范围页数 2")).toBeVisible();
    expect(screen.getByText("课时划分范围 scope-version-1")).toBeVisible();
    await waitFor(() =>
      expect(listPages).toHaveBeenCalledWith({
        materialId,
        parseVersionId,
        projectId,
      }),
    );
  });

  it("does not expose another textbook parse scope to lesson division", async () => {
    workflow.approvedVersionId = "scope-version-1";
    workflow.scopeMaterialId = "01960000-0000-7000-8000-000000000099";
    workflow.scopeParseVersionId = "01960000-0000-7000-8000-000000000098";
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({
      asset: { status: "active" } as materialsApi.FileAssetDto,
    });
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockResolvedValue([
      {
        id: parseVersionId,
        page_count: 2,
        status: "succeeded",
      } as materialsApi.MaterialParseVersionDto,
    ]);
    vi.spyOn(materialsApi, "listMaterialParsePages").mockResolvedValue([
      { page_number: 1 } as materialsApi.MaterialParsePageDto,
    ]);

    renderPage(`/app/projects/${projectId}/materials/${materialId}`);

    expect(await screen.findByText("课时划分范围 未批准")).toBeVisible();
  });
});
