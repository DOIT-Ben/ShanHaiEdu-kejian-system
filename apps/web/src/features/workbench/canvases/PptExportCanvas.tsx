import { Link } from "react-router";
import { Download, Play } from "lucide-react";
import { useNodeRunDetail, useStartNode } from "@/features/node-runs";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { FailedPanel, RunningPanel, StepScaffold } from "../parts";

/** 导出 PPT：正文完成后导出 pptx（可编辑文字与数学图形）。 */
export function PptExportCanvas() {
  const { projectId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const start = useStartNode(nodeRun?.id ?? "");

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;

  const startExport = () =>
    start.mutate(undefined, {
      onError: (error) => toast({ tone: "danger", title: "无法导出", description: error.message }),
    });

  return (
    <StepScaffold
      title="导出 PPT"
      description="导出为可编辑的 PPTX：文字与数学图形在 Office / WPS 中可继续修改。"
      status={status}
      primaryAction={
        status === "ready" || status === "failed" ? (
          <Button onClick={startExport} loading={start.isPending} loadingText="正在导出…">
            <Play className="size-4" aria-hidden />
            导出 PPT
          </Button>
        ) : status === "approved" ? (
          <Button asChild>
            <Link to={`/app/projects/${projectId}/results`}>
              <Download className="size-4" aria-hidden />
              去下载
            </Link>
          </Button>
        ) : undefined
      }
    >
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在导出 PPT" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "导出失败。"}
          onRetry={startExport}
          retrying={start.isPending}
        />
      ) : status === "not_ready" || status === "disabled" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          正文页面全部完成后即可导出。
        </p>
      ) : status === "approved" ? (
        <p className="mx-auto max-w-md rounded-lg border border-success-200 bg-success-50 p-6 text-center text-sm text-ink">
          PPT 已导出。可在「素材与成果」下载，或在「项目交付」打包全部作品。
        </p>
      ) : (
        <p className="mx-auto max-w-md rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          点击「导出 PPT」。
        </p>
      )}
    </StepScaffold>
  );
}
