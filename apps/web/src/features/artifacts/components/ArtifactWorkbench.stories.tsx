import type { Meta, StoryObj } from "@storybook/react-vite";
import type { ArtifactDto, ArtifactVersionDto } from "@/features/artifacts/api/artifactsApi";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";

const submittedVersion = {
  content: {},
  content_hash: "sha256:lesson-plan-version-2",
  context_snapshot_id: null,
  created_at: "2026-07-22T03:00:00Z",
  created_by: "30000000-0000-4000-8000-000000000005",
  id: "30000000-0000-4000-8000-000000000004",
  prompt_snapshot_id: null,
  render_summary: {},
  source_kind: "manual",
  source_node_run_id: null,
  validation_report: {},
  version_no: 2,
} satisfies ArtifactVersionDto;

const draftArtifact = {
  artifact_key: "lesson-plan/main",
  artifact_type: "lesson_plan",
  branch_key: "lesson_plan",
  content_definition_version_id: "30000000-0000-4000-8000-000000000003",
  created_at: "2026-07-22T02:00:00Z",
  current_approved_version: null,
  current_draft: {
    autosaved_at: "2026-07-22T02:55:00Z",
    based_on_version_id: null,
    content: {},
    draft_branch: "main",
    id: "30000000-0000-4000-8000-000000000006",
    lock_version: 4,
    validation_report: {},
  },
  current_submitted_version: null,
  id: "30000000-0000-4000-8000-000000000001",
  lesson_unit_id: "30000000-0000-4000-8000-000000000002",
  lock_version: 4,
  project_id: "30000000-0000-4000-8000-000000000007",
  stale_reason: null,
  status: "draft",
  updated_at: "2026-07-22T02:55:00Z",
} satisfies ArtifactDto;

const meta = {
  title: "Runtime/Artifact 工作台",
  component: ArtifactWorkbench,
  tags: ["core-viewport"],
  args: {
    artifact: draftArtifact,
    title: "课时教案",
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-5xl p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ArtifactWorkbench>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Draft: Story = {};
export const Conflict: Story = {
  args: { conflictMessage: "服务器草稿已更新，请刷新后重新应用本次编辑。" },
};
export const Archived: Story = {
  args: { artifact: { ...draftArtifact, status: "archived" } },
};
export const InReview: Story = {
  args: {
    artifact: {
      ...draftArtifact,
      current_submitted_version: submittedVersion,
      status: "in_review",
    },
  },
};
export const Approved: Story = {
  args: {
    artifact: {
      ...draftArtifact,
      current_approved_version: submittedVersion,
      current_submitted_version: submittedVersion,
      status: "approved",
    },
  },
};
