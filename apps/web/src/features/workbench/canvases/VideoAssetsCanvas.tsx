import { useNavigate } from "react-router";
import { useMutation } from "@tanstack/react-query";
import { Images, Play } from "lucide-react";
import { client, unwrap } from "@/shared/api";
import { createIdempotencyKey } from "@/shared/lib/idempotency";
import { useNodeRunDetail, useStartNode } from "@/features/node-runs";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun } from "../context";
import { FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";

/**
 * 制作镜头图片：四类资产（场景/角色/道具/关键帧）批量制作，
 * 走通用创作中心（创作包 → 本次创作批次）。
 */
export function VideoAssetsCanvas() {
  const navigate = useNavigate();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const start = useStartNode(nodeRun?.id ?? "");

  const goToStudio = useMutation({
    mutationFn: async () => {
      const pkg = unwrap(
        await client.POST("/node-runs/{node_run_id}/creation-packages", {
          params: { path: { node_run_id: nodeRun!.id }, header: { "Idempotency-Key": createIdempotencyKey("package") } },
        }),
      );
      const batch = unwrap(
        await client.POST("/creation-batches", {
          body: {
            studio_type: "image",
            title: "镜头图片批量制作",
            creation_package_id: pkg.data.package_id,
          },
          params: { header: { "Idempotency-Key": createIdempotencyKey("batch") } },
        }),
      );
      return batch.data;
    },
    onSuccess: (batch) => {
      void navigate(`/app/creation/batches/${batch.id}`);
    },
    onError: (error) => toast({ tone: "danger", title: "无法创建批次", description: error.message }),
  });

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;

  const startGeneration = () =>
    start.mutate(undefined, {
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title="制作镜头图片"
      description="按画面风格准备场景、角色、道具与关键帧四类图片素材。"
      status={status}
      primaryAction={
        status === "ready" || status === "review_required" || status === "partially_completed" ? (
          <Button onClick={() => goToStudio.mutate()} loading={goToStudio.isPending} loadingText="正在准备…">
            <Images className="size-4" aria-hidden />
            去创作中心批量制作
          </Button>
        ) : status === "failed" ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            重新准备清单
          </Button>
        ) : undefined
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在整理待生成清单" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成失败。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : status === "not_ready" || status === "disabled" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          画面风格确定后，即可批量制作镜头图片。
        </p>
      ) : (
        <div className="mx-auto max-w-2xl rounded-lg border border-line-subtle bg-surface p-8 text-center shadow-card">
          <Images className="mx-auto size-10 text-brand-500" aria-hidden />
          <p className="mt-4 text-base font-medium text-ink-strong">待生成内容已就绪</p>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">
            系统已按镜头整理出需要的图片清单（场景、角色、道具、关键帧）。
            在创作中心里逐项生成、挑选并保存回项目，完成后回到「制作视频片段」。
          </p>
        </div>
      )}
    </StepScaffold>
  );
}
