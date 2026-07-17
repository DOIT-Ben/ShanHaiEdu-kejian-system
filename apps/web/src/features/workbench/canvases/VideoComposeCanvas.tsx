import { Link } from "react-router";
import { Clapperboard, Play } from "lucide-react";
import { useNodeRunDetail, useNodeResults, useStartNode } from "@/features/node-runs";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";

/** 合成完整视频：全部镜头采用后 FFmpeg 合成（含配音字幕）。 */
export function VideoComposeCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const { data: results } = useNodeResults(nodeRun?.id ?? null, "final_video");
  const start = useStartNode(nodeRun?.id ?? "");

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const finalResult = (results ?? [])[0] ?? null;

  const startCompose = () =>
    start.mutate(undefined, {
      onSuccess: () => toast({ tone: "info", title: "开始合成", description: "包含配音与字幕，通常需要几分钟。" }),
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title="合成完整视频"
      description="把已采用的镜头片段与配音、字幕合成为一支课堂导入视频。"
      status={status}
      primaryAction={
        status === "ready" || status === "failed" ? (
          <Button onClick={startCompose} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            开始合成
          </Button>
        ) : undefined
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在合成视频" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "合成失败。"}
          onRetry={startCompose}
          retrying={start.isPending}
        />
      ) : status === "not_ready" || status === "disabled" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          所有镜头的片段都采用后，才能合成完整视频。
          <Link
            to={`/app/projects/${projectId}/lessons/${lessonId}/work/video-clips`}
            className="ml-1 font-medium text-brand-600 hover:underline"
          >
            去制作视频片段
          </Link>
        </p>
      ) : (
        <div className="mx-auto max-w-2xl space-y-5">
          {finalResult ? (
            <figure className="overflow-hidden rounded-lg border border-line-subtle shadow-card">
              <div className="sh-player-surface flex items-center justify-center">
                {finalResult.preview_url ? (
                  <img src={finalResult.preview_url} alt="课堂导入视频预览" className="max-h-[52vh] w-full object-contain" />
                ) : (
                  <div className="flex h-64 w-full items-center justify-center text-white/60">
                    <Clapperboard className="size-10" aria-hidden />
                  </div>
                )}
              </div>
              <figcaption className="flex items-center justify-between border-t border-line-subtle bg-surface px-4 py-3 text-sm">
                <span className="text-ink">
                  课堂导入视频{finalResult.duration_seconds ? ` · ${finalResult.duration_seconds} 秒` : ""}
                </span>
                <Button asChild variant="secondary" size="sm">
                  <Link to={`/app/projects/${projectId}/results`}>在素材与成果中查看</Link>
                </Button>
              </figcaption>
            </figure>
          ) : status === "approved" ? (
            <p className="rounded-lg border border-success-200 bg-success-50 p-4 text-sm text-ink">
              合成完成。可到「素材与成果」下载，或在「项目交付」打包全部作品。
            </p>
          ) : (
            <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
              点击「开始合成」。
            </p>
          )}
        </div>
      )}
    </StepScaffold>
  );
}
