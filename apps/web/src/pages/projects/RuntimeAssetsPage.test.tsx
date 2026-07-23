import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as assetsApi from "@/features/assets/api/assetsApi";
import { RuntimeAssetsPage } from "@/pages/projects/RuntimeAssetsPage";
import { configureCsrfTokenProvider } from "@/shared/api/client";

vi.mock("@/shared/api/useProjectEvents", () => ({ useProjectEvents: vi.fn() }));

const projectId = "01960000-0000-7000-8000-000000000001";
const slot = {
  active_bindings: [
    { id: "binding-1", file_asset_version_id: "file-version-old", is_active: true },
  ],
  asset_type: "image",
  cardinality: "many",
  id: "slot-1",
  required: true,
  slot_key: "ppt.cover",
  status: "satisfied",
  target_contract: { allowed_mime_types: ["image/png"], require_clean_scan: true },
} as assetsApi.ProjectAssetSlotDto;

function renderAssetsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[
          `/app/projects/${projectId}/assets?fileVersionId=file-version-new&assetLabel=${encodeURIComponent("课堂封面")}`,
        ]}
      >
        <Routes>
          <Route element={<RuntimeAssetsPage />} path="/app/projects/:projectId/assets" />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RuntimeAssetsPage idempotency", () => {
  beforeEach(() => {
    configureCsrfTokenProvider(() => "csrf-test-token");
    vi.spyOn(assetsApi, "listProjectAssetSlots").mockResolvedValue({ items: [slot] });
    vi.spyOn(assetsApi, "getProjectAssetPackage").mockResolvedValue({
      items: [slot],
      projectId,
    });
  });

  afterEach(() => {
    configureCsrfTokenProvider(null);
    vi.restoreAllMocks();
  });

  it("模糊失败后重试绑定会复用同一个幂等键", async () => {
    const bind = vi
      .spyOn(assetsApi, "bindProjectAsset")
      .mockRejectedValueOnce(new TypeError("response lost"))
      .mockResolvedValueOnce({ id: "binding-2" } as assetsApi.AssetBindingDto);
    renderAssetsPage();

    const user = userEvent.setup();
    const bindButton = await screen.findByRole("button", { name: "放入图片位置 1" });
    await user.click(bindButton);
    expect(await screen.findByRole("alert")).toHaveTextContent("素材没有更新");
    await user.click(bindButton);

    await waitFor(() => expect(bind).toHaveBeenCalledTimes(2));
    expect(bind.mock.calls[1]?.[0].idempotencyKey).toBe(bind.mock.calls[0]?.[0].idempotencyKey);
    expect(bind.mock.calls[0]?.[0].input.replace_mode).toBe("append");
  });

  it("模糊失败后重试解绑会复用同一个幂等键", async () => {
    const unbind = vi
      .spyOn(assetsApi, "unbindProjectAsset")
      .mockRejectedValueOnce(new TypeError("response lost"))
      .mockResolvedValueOnce({ id: "binding-1", is_active: false } as assetsApi.AssetBindingDto);
    renderAssetsPage();

    const user = userEvent.setup();
    const unbindButton = await screen.findByRole("button", { name: "移除图片素材 1" });
    await user.click(unbindButton);
    expect(await screen.findByRole("alert")).toHaveTextContent("素材没有更新");
    await user.click(unbindButton);

    await waitFor(() => expect(unbind).toHaveBeenCalledTimes(2));
    expect(unbind.mock.calls[1]?.[0].idempotencyKey).toBe(unbind.mock.calls[0]?.[0].idempotencyKey);
  });

  it("读取全部分页素材位置", async () => {
    const secondSlot = {
      ...slot,
      active_bindings: [],
      id: "slot-2",
      status: "empty",
    } as assetsApi.ProjectAssetSlotDto;
    vi.mocked(assetsApi.listProjectAssetSlots)
      .mockReset()
      .mockResolvedValueOnce({ items: [slot], nextCursor: "page-2" })
      .mockResolvedValueOnce({ items: [secondSlot] });
    renderAssetsPage();

    expect(await screen.findByRole("heading", { name: "图片位置 2" })).toBeVisible();
    expect(assetsApi.listProjectAssetSlots).toHaveBeenNthCalledWith(2, {
      cursor: "page-2",
      projectId,
    });
  });

  it("单侧读取失败时保留资产包中的成功数据", async () => {
    vi.mocked(assetsApi.listProjectAssetSlots)
      .mockReset()
      .mockRejectedValueOnce(new TypeError("slots unavailable"));
    renderAssetsPage();

    expect(await screen.findByText("素材包包含 1 个素材位置。")).toBeVisible();
    expect(screen.getByRole("button", { name: "放入图片位置 1" })).toBeEnabled();
    expect(screen.getByText(/部分素材信息未能更新/)).toBeVisible();
  });
});
