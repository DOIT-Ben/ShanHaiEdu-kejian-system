import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ProjectAssetSlotDto } from "@/features/assets/api/assetsApi";
import { ProjectAssetSlotsPanel } from "@/features/assets/components/ProjectAssetSlotsPanel";

const slot = {
  active_bindings: [
    { id: "binding-1", file_asset_version_id: "file-version-old", is_active: true },
  ],
  asset_type: "image",
  cardinality: "one",
  id: "slot-1",
  required: true,
  slot_key: "ppt.cover",
  status: "satisfied",
  target_contract: { allowed_mime_types: ["image/png"], require_clean_scan: true },
} as ProjectAssetSlotDto;

describe("ProjectAssetSlotsPanel", () => {
  it("提交绑定合同并允许解绑已有素材", async () => {
    const user = userEvent.setup();
    const onBind = vi.fn();
    const onUnbind = vi.fn();
    render(
      <ProjectAssetSlotsPanel
        onBind={onBind}
        onUnbind={onUnbind}
        selectedAsset={{ fileAssetVersionId: "file-version-new", label: "课堂封面" }}
        slots={[slot]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "放入图片位置 1" }));
    expect(onBind).toHaveBeenCalledWith(
      "slot-1",
      expect.objectContaining({
        file_asset_version_id: "file-version-new",
        replace_mode: "replace_active",
      }),
    );

    await user.click(screen.getByRole("button", { name: "移除图片素材 1" }));
    expect(onUnbind).toHaveBeenCalledWith("binding-1");
    expect(screen.queryByText("ppt.cover")).not.toBeInTheDocument();
    expect(screen.queryByText("file-version-old")).not.toBeInTheDocument();
  });
});
