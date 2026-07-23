import type { Meta, StoryObj } from "@storybook/react-vite";
import { AlertTriangle, CheckCircle2, LoaderCircle } from "lucide-react";
import { PptCoverArtwork } from "@/features/workbench/components/PptCoverArtwork";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type PptStoryState = "completed" | "conflict" | "error" | "loading" | "partial" | "running";

const pptStateCopy = {
  completed: {
    detail: "页面与封面已经准备好，可以进入最终确认。",
    status: "approved",
    title: "PPT 已完成",
  },
  conflict: {
    detail: "服务器版本已经变化，请刷新后再继续编辑。",
    status: "stale",
    title: "PPT 已有更新",
  },
  error: {
    detail: "请检查网络后重试，现有页面不会被覆盖。",
    status: "failed",
    title: "PPT 暂时无法读取",
  },
  loading: {
    detail: "正在从项目快照读取页面与封面。",
    status: "queued",
    title: "正在读取 PPT 状态",
  },
  partial: {
    detail: "12 页中有 10 页可用，2 页需要重新处理。",
    status: "partially_completed",
    title: "PPT 部分页面已完成",
  },
  running: {
    detail: "任务已经提交，可以离开页面后再回来查看。",
    status: "running",
    title: "正在生成 PPT",
  },
} as const;

function PptStatePreview({ state }: { state: PptStoryState }) {
  const copy = pptStateCopy[state];
  const Icon =
    state === "completed"
      ? CheckCircle2
      : state === "loading" || state === "running"
        ? LoaderCircle
        : AlertTriangle;
  return (
    <section
      aria-busy={state === "loading" || state === "running"}
      aria-label={copy.title}
      className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-5"
      role={state === "error" || state === "conflict" ? "alert" : "status"}
    >
      <div className="flex min-w-0 items-start gap-3">
        <Icon
          aria-hidden="true"
          className={`mt-0.5 size-5 shrink-0 ${state === "loading" || state === "running" ? "animate-spin motion-reduce:animate-none" : ""}`}
        />
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-[var(--sh-ink-strong)]">{copy.title}</h2>
          <p className="mt-1 text-sm leading-6 text-[var(--sh-ink-muted)]">{copy.detail}</p>
        </div>
        <StatusBadge status={copy.status} />
      </div>
      {state === "loading" ? (
        <div className="mt-5 aspect-video animate-pulse rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
      ) : (
        <div className="mt-5">
          <PptCoverArtwork demo variant={1}>
            <p className="text-sm font-medium">六年级数学</p>
            <h3 className="mt-2 text-3xl font-semibold">认识百分数</h3>
          </PptCoverArtwork>
        </div>
      )}
    </section>
  );
}

const meta = {
  title: "PPT/封面预览",
  component: PptCoverArtwork,
  tags: ["core-viewport"],
  args: {
    children: (
      <>
        <p className="text-sm font-medium">六年级数学</p>
        <h2 className="mt-2 text-3xl font-semibold">认识百分数</h2>
      </>
    ),
    demo: true,
    variant: 1,
  },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-[760px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof PptCoverArtwork>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ClassroomArtwork: Story = {};
export const GeneratedPlaceholder: Story = { args: { demo: false, variant: 2 } };
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
export const Loading: Story = { render: () => <PptStatePreview state="loading" /> };
export const Error: Story = { render: () => <PptStatePreview state="error" /> };
export const Conflict: Story = { render: () => <PptStatePreview state="conflict" /> };
export const Running: Story = { render: () => <PptStatePreview state="running" /> };
export const PartialSuccess: Story = { render: () => <PptStatePreview state="partial" /> };
export const Completed: Story = { render: () => <PptStatePreview state="completed" /> };
