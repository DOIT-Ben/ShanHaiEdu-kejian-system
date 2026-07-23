import type { Meta, StoryObj } from "@storybook/react-vite";
import { AlertTriangle, CheckCircle2, LoaderCircle } from "lucide-react";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type VideoStoryState = "completed" | "conflict" | "error" | "loading" | "partial" | "running";

const videoStateCopy = {
  completed: {
    detail: "画面与字幕已经准备好，可以进入最终确认。",
    status: "approved",
    title: "视频已完成",
  },
  conflict: {
    detail: "服务器版本已经变化，请刷新后再继续编辑。",
    status: "stale",
    title: "视频版本已更新",
  },
  error: {
    detail: "请检查网络后重试，现有分镜和素材不会被覆盖。",
    status: "failed",
    title: "视频暂时无法读取",
  },
  loading: {
    detail: "正在读取视频、字幕与任务状态。",
    status: "queued",
    title: "正在读取视频状态",
  },
  partial: {
    detail: "画面已经生成，字幕仍需要重新处理。",
    status: "partially_completed",
    title: "视频部分内容已完成",
  },
  running: {
    detail: "任务已经提交，可以离开页面后再回来查看。",
    status: "running",
    title: "正在生成视频",
  },
} as const;

function VideoStatePreview({ state }: { state: VideoStoryState }) {
  const copy = videoStateCopy[state];
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
          <VideoScenePreview topic="百分数的意义" variant={0} />
        </div>
      )}
    </section>
  );
}

const meta = {
  title: "视频/关键帧预览",
  component: VideoScenePreview,
  tags: ["core-viewport"],
  args: { topic: "百分数的意义", variant: 0 },
  decorators: [
    (Story) => (
      <div className="mx-auto max-w-[720px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof VideoScenePreview>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Standard: Story = {};
export const Compact: Story = { args: { compact: true } };
export const Narrow390: Story = {
  parameters: { viewport: { defaultViewport: "narrow390" } },
};
export const Loading: Story = { render: () => <VideoStatePreview state="loading" /> };
export const Error: Story = { render: () => <VideoStatePreview state="error" /> };
export const Conflict: Story = { render: () => <VideoStatePreview state="conflict" /> };
export const Running: Story = { render: () => <VideoStatePreview state="running" /> };
export const PartialSuccess: Story = { render: () => <VideoStatePreview state="partial" /> };
export const Completed: Story = { render: () => <VideoStatePreview state="completed" /> };
