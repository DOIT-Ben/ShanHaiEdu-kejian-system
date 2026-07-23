import type { Meta, StoryObj } from "@storybook/react-vite";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";

const runningJob = {
  created_at: "2026-07-22T05:00:00Z",
  error_code: null,
  id: "50000000-0000-4000-8000-000000000001",
  job_type: "material_parse",
  progress_message: "正在核对第 42 页",
  progress_percent: 56,
  project_id: "50000000-0000-4000-8000-000000000002",
  status: "running",
  updated_at: "2026-07-22T05:03:00Z",
} satisfies GenerationJobDto;

const meta = {
  title: "Runtime/Generation Job 状态",
  component: GenerationJobPanel,
  tags: ["core-viewport"],
  args: {
    job: runningJob,
    onCancel: () => undefined,
    onRefresh: () => undefined,
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-4xl p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof GenerationJobPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Running: Story = {};
export const Loading: Story = { args: { job: undefined, loading: true } };
export const Empty: Story = { args: { job: undefined } };
export const Error: Story = {
  args: { errorMessage: "任务状态暂时无法读取。", job: undefined },
};
export const Failed: Story = {
  args: {
    job: {
      ...runningJob,
      error_code: "MATERIAL_PARSE_FAILED",
      progress_message: "教材解析失败",
      progress_percent: 68,
      status: "failed",
    },
  },
};
export const CancelRequested: Story = {
  args: {
    job: {
      ...runningJob,
      progress_message: "等待当前处理步骤结束",
      status: "cancel_requested",
    },
  },
};
export const Cancelled: Story = {
  args: {
    job: {
      ...runningJob,
      progress_message: "任务已按请求取消",
      status: "cancelled",
    },
  },
};
export const Completed: Story = {
  args: {
    job: {
      ...runningJob,
      progress_message: "教材解析完成",
      progress_percent: 100,
      status: "succeeded",
    },
  },
};
