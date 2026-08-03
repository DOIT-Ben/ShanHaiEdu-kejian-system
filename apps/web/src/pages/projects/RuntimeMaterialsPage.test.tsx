import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import * as materialsApi from "@/features/materials/api/materialsApi";
import { RuntimeMaterialsPage } from "@/pages/projects/RuntimeMaterialsPage";
import type * as ApiClientModule from "@/shared/api/client";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));
vi.mock("@/shared/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof ApiClientModule>()),
  isCsrfTokenAvailable: () => true,
}));

const projectId = "01960000-0000-7000-8000-000000000001";
const materialId = "01960000-0000-7000-8000-000000000002";
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
  id: "01960000-0000-7000-8000-000000000201",
  page_count: 8,
  parser_name: "pdf-parser",
  parser_version: "1.0",
  status: "succeeded",
  version_no: 1,
} as materialsApi.MaterialParseVersionDto;

function renderMaterialsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/app/projects/${projectId}/materials/${materialId}`]}>
        <Routes>
          <Route
            element={<RuntimeMaterialsPage />}
            path="/app/projects/:projectId/materials/:materialId"
          />
          <Route element={<SetupDestination />} path="/app/projects/:projectId/setup" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function SetupDestination() {
  const location = useLocation();
  return <p>setup destination {location.search}</p>;
}

describe("RuntimeMaterialsPage partial reads", () => {
  afterEach(() => vi.restoreAllMocks());

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

  it("最新 exact 解析失败后启动新任务并进入现有 setup 进度页", async () => {
    const exactAsset = {
      ...asset,
      current_version: {
        ...asset.current_version,
        id: "01960000-0000-7000-8000-000000000301",
      },
    };
    const failed: materialsApi.MaterialParseVersionDto = {
      ...parseVersion,
      error_code: "PDF_DAMAGED",
      file_asset_version_id: exactAsset.current_version.id,
      status: "failed",
      version_no: 2,
    };
    vi.spyOn(materialsApi, "listProjectTextbookMaterials").mockResolvedValue([]);
    vi.spyOn(materialsApi, "getSourceMaterialFileAsset").mockResolvedValue({ asset: exactAsset });
    vi.spyOn(materialsApi, "listMaterialParseVersions").mockResolvedValue([failed]);
    const retry = vi.spyOn(materialsApi, "retryMaterialParse").mockResolvedValue({
      events_url: "/api/v2/generation-jobs/job-retry/events/stream",
      job_id: "job-retry",
      status: "queued",
    });
    renderMaterialsPage();

    fireEvent.click(await screen.findByRole("button", { name: "重新解析" }));

    await waitFor(() => expect(retry).toHaveBeenCalledOnce());
    const retryInput = retry.mock.calls[0]?.[0];
    expect(retryInput?.fileAssetVersionId).toBe(exactAsset.current_version.id);
    expect(typeof retryInput?.idempotencyKey).toBe("string");
    expect(retryInput?.materialId).toBe(materialId);
    expect(retryInput?.projectId).toBe(projectId);
    expect(await screen.findByText(/setup destination/)).toHaveTextContent("jobId=job-retry");
    expect(screen.getByText(/setup destination/)).toHaveTextContent(`materialId=${materialId}`);
  });
});
