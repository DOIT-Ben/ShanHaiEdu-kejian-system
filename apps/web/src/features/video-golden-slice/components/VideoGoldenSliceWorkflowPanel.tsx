import { CheckCircle2, Film, RefreshCw, Save } from "lucide-react";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { useVideoGoldenSlice } from "@/features/video-golden-slice/hooks/useVideoGoldenSlice";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { resolveApiResourceUrl } from "@/shared/api/config";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

const videoFailureMessages: Record<string, string> = {
  MODEL_AUTHENTICATION_FAILED: "视频服务认证失败，当前任务未产生候选短片。",
  MODEL_RATE_LIMITED: "视频服务当前繁忙，请稍后重新生成。",
  MODEL_TIMEOUT: "视频服务等待超时，请稍后重新生成。",
  VIDEO_DURATION_INVALID: "生成文件不是约 6 秒的短片，已拒绝采用。",
  VIDEO_FILE_INVALID: "生成文件未通过 MP4 完整性校验，已拒绝采用。",
  VIDEO_FILE_UNAVAILABLE: "生成文件暂时无法读取，请稍后重新生成。",
  VIDEO_INPUTS_INVALID: "课堂导入方案或正式关键帧已经变化，请刷新后重新生成。",
  VIDEO_PROVIDER_FAILED: "视频服务未能完成本次生成，请稍后重试。",
  VIDEO_WORKER_FAILED: "短片处理没有完成，请稍后重新生成。",
};

function failureMessage(code: string | null | undefined) {
  return (code && videoFailureMessages[code]) || "短片生成没有完成，请刷新后重新生成。";
}

export function VideoGoldenSliceWorkflowPanel({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}) {
  const runtime = useVideoGoldenSlice(projectId, lessonId);
  const slice = runtime.query.data;
  const candidate = slice?.candidate;
  const actionError =
    runtime.startMutation.error ??
    runtime.adoptMutation.error ??
    runtime.saveMutation.error ??
    runtime.cancelMutation.error;

  if (runtime.query.isLoading) {
    return (
      <div
        className="mt-5 h-72 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
        role="status"
      >
        <span className="sr-only">正在读取课堂视频</span>
      </div>
    );
  }
  if (runtime.query.isError || !slice) {
    return (
      <section
        className="mt-5 border-y border-[var(--sh-line-subtle)] py-8"
        aria-labelledby="video-unavailable-title"
      >
        <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="video-unavailable-title">
          课堂视频暂时无法读取
        </h2>
        <p className="mt-2 text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(runtime.query.error, "请确认已经采用课堂导入方案并绑定正式关键帧。")}
        </p>
        <Button className="mt-4" onClick={() => void runtime.query.refetch()} variant="secondary">
          <RefreshCw aria-hidden="true" />
          重新读取
        </Button>
      </section>
    );
  }

  const liveJob = Boolean(
    slice.job && !["succeeded", "failed", "cancelled"].includes(slice.job.status),
  );
  const writeReady = isCsrfTokenAvailable();

  return (
    <div className="mt-5 space-y-5">
      <section
        className="border-y border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] px-5 py-5 md:px-7"
        aria-labelledby="video-golden-title"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">课堂导入短片</p>
            <h2
              className="mt-1 text-lg font-semibold text-[var(--sh-ink-strong)]"
              id="video-golden-title"
            >
              6 秒黄金切片
            </h2>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-[var(--sh-ink-muted)]">
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 aria-hidden="true" className="size-4 text-[var(--sh-success)]" />
                课堂导入已采用
              </span>
              <span className="inline-flex items-center gap-1.5">
                <CheckCircle2 aria-hidden="true" className="size-4 text-[var(--sh-success)]" />
                正式关键帧已绑定
              </span>
            </div>
          </div>
          <Button
            disabled={!writeReady || liveJob || !slice.keyframe_file_asset_version_id}
            loading={runtime.startMutation.isPending}
            loadingText="正在启动生成"
            onClick={() => runtime.startMutation.mutate()}
          >
            <Film aria-hidden="true" />
            生成 6 秒短片
          </Button>
        </div>
      </section>

      {slice.job ? (
        <GenerationJobPanel
          cancelPending={runtime.cancelMutation.isPending}
          errorMessage={
            slice.job.status === "failed" ? failureMessage(slice.job.error_code) : undefined
          }
          job={slice.job}
          loading={runtime.query.isFetching}
          onCancel={liveJob && writeReady ? () => runtime.cancelMutation.mutate() : undefined}
          onRefresh={() => void runtime.query.refetch()}
          progressLabel="短片生成进度"
          title="短片生成进度"
        />
      ) : null}

      {candidate ? (
        <section
          className="grid gap-5 border-b border-[var(--sh-line-default)] pb-6 lg:grid-cols-[minmax(0,720px)_minmax(240px,1fr)] lg:items-start"
          aria-labelledby="video-candidate-title"
        >
          <video
            aria-label="6 秒课堂导入短片"
            className="aspect-video w-full bg-black object-contain"
            controls
            preload="metadata"
            src={resolveApiResourceUrl(candidate.playback_url)}
          />
          <div className="min-w-0 lg:pt-2">
            <div className="flex items-center gap-2 text-[var(--sh-ink-strong)]">
              <Film aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
              <h2 className="font-semibold" id="video-candidate-title">
                生成候选
              </h2>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              {Math.round(candidate.duration_ms / 100) / 10} 秒，MP4，
              {Math.ceil(candidate.byte_size / 1024)} KB
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {candidate.saved_binding_id ? (
                <span className="inline-flex min-h-10 items-center gap-2 text-sm font-semibold text-[var(--sh-success-strong)]">
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  已保存到当前课时
                </span>
              ) : candidate.adoption_id ? (
                <Button
                  loading={runtime.saveMutation.isPending}
                  loadingText="正在保存"
                  onClick={() => runtime.saveMutation.mutate(candidate.adoption_id ?? "")}
                >
                  <Save aria-hidden="true" />
                  保存到当前课时
                </Button>
              ) : (
                <Button
                  disabled={!writeReady}
                  loading={runtime.adoptMutation.isPending}
                  loadingText="正在采用"
                  onClick={() => runtime.adoptMutation.mutate(candidate.result_id)}
                >
                  <CheckCircle2 aria-hidden="true" />
                  采用这段短片
                </Button>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {actionError ? (
        <p className="text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(actionError, "当前操作没有完成，请刷新后重试。")}
        </p>
      ) : null}
    </div>
  );
}
