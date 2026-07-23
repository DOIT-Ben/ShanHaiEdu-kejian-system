import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as materialsApi from "@/features/materials/api/materialsApi";
import { RuntimeMaterialsPage } from "@/pages/projects/RuntimeMaterialsPage";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));

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
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
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
});
