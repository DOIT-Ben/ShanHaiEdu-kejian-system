import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ProjectAssetSlotDto } from "@/features/assets/api/assetsApi";
import { ProjectAssetSlotsPanel } from "@/features/assets/components/ProjectAssetSlotsPanel";

const emptySlot = {
  active_bindings: [],
  asset_type: "image",
  cardinality: "one",
  id: "40000000-0000-4000-8000-000000000001",
  lesson_unit_id: "40000000-0000-4000-8000-000000000002",
  project_id: "40000000-0000-4000-8000-000000000003",
  required: true,
  slot_key: "ppt_cover",
  status: "empty",
  target_contract: {
    allowed_mime_types: ["image/png", "image/webp"],
    require_clean_scan: true,
  },
} satisfies ProjectAssetSlotDto;

const boundSlot = {
  ...emptySlot,
  active_bindings: [
    {
      bound_at: "2026-07-22T04:00:00Z",
      bound_by: "40000000-0000-4000-8000-000000000004",
      file_asset_version_id: "40000000-0000-4000-8000-000000000005",
      id: "40000000-0000-4000-8000-000000000006",
      is_active: true,
      position: 0,
      project_asset_slot_id: emptySlot.id,
      source_artifact_version_id: null,
      unbound_at: null,
      unbound_by: null,
    },
  ],
  status: "satisfied",
} satisfies ProjectAssetSlotDto;

const meta = {
  title: "Runtime/项目素材槽位",
  component: ProjectAssetSlotsPanel,
  tags: ["core-viewport"],
  args: {
    onBind: () => undefined,
    onUnbind: () => undefined,
    selectedAsset: {
      fileAssetVersionId: "40000000-0000-4000-8000-000000000009",
      label: "百分数百格图",
    },
    slots: [emptySlot],
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-4xl p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProjectAssetSlotsPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const AwaitingBinding: Story = {};
export const Empty: Story = { args: { slots: [] } };
export const Error: Story = { args: { errorMessage: "素材包刷新失败，请稍后重试。" } };
export const Completed: Story = { args: { slots: [boundSlot] } };
export const ReadOnly: Story = { args: { slots: [boundSlot], writeDisabled: true } };
export const NoSelection: Story = { args: { selectedAsset: undefined } };
