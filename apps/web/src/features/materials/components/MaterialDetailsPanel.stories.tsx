import type { Meta, StoryObj } from "@storybook/react-vite";
import type { FileAssetDto, MaterialParseVersionDto } from "@/features/materials/api/materialsApi";
import { MaterialDetailsPanel } from "@/features/materials/components/MaterialDetailsPanel";

const fileAsset = {
  asset_key: "textbook/source.pdf",
  asset_kind: "source_material",
  current_version: {
    byte_size: 18_350_080,
    created_at: "2026-07-22T02:00:00Z",
    derived_from_version_id: null,
    duration_ms: null,
    height: null,
    id: "10000000-0000-4000-8000-000000000002",
    mime_type: "application/pdf",
    page_count: 128,
    scan_status: "clean",
    sha256: "4f6d9a2b7c8e1d3f5a6b0c2e4d7f9a1b3c5e6d8f0a2b4c6d8e0f1a3b5c7d9e2f",
    version_no: 1,
    width: null,
  },
  id: "10000000-0000-4000-8000-000000000001",
  lock_version: 2,
  retention_class: "project_source",
  status: "active",
} satisfies FileAssetDto;

const completedParse = {
  completed_at: "2026-07-22T02:04:00Z",
  created_at: "2026-07-22T02:01:00Z",
  error_code: null,
  file_asset_version_id: fileAsset.current_version.id,
  generation_job_id: "10000000-0000-4000-8000-000000000004",
  id: "10000000-0000-4000-8000-000000000003",
  page_count: 128,
  parser_name: "document-parser",
  parser_version: "2.4.0",
  source_material_id: fileAsset.id,
  started_at: "2026-07-22T02:01:30Z",
  status: "succeeded",
  text_checksum: "sha256:lesson-text-v1",
  validation_report: {},
  version_no: 1,
} satisfies MaterialParseVersionDto;

const meta = {
  title: "Runtime/教材文件与解析",
  component: MaterialDetailsPanel,
  tags: ["core-viewport"],
  args: {
    asset: fileAsset,
    onRefresh: () => undefined,
    parseVersions: [completedParse],
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-4xl p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof MaterialDetailsPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Completed: Story = {};
export const Loading: Story = { args: { asset: undefined, loading: true, parseVersions: [] } };
export const Empty: Story = { args: { asset: undefined, parseVersions: [] } };
export const Running: Story = {
  args: {
    parseVersions: [
      {
        ...completedParse,
        completed_at: null,
        error_code: null,
        page_count: null,
        started_at: "2026-07-22T02:01:30Z",
        status: "running",
        text_checksum: null,
      },
    ],
  },
};
export const Failed: Story = {
  args: {
    errorMessage: "解析记录刷新失败，请稍后重试。",
    parseVersions: [
      {
        ...completedParse,
        error_code: "PDF_TEXT_EXTRACTION_FAILED",
        page_count: null,
        status: "failed",
        text_checksum: null,
      },
    ],
  },
};
