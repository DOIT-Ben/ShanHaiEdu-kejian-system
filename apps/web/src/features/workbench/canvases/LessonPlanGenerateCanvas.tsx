import { Link } from "react-router";
import { ArrowRight, Play } from "lucide-react";
import { useNodeRunDetail, useStartNode } from "@/features/node-runs";
import { PromptSection } from "@/features/prompt-editing";
import { AppError } from "@/shared/api";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";

/** 生成教案：查看/编辑完整生成指令 → 开始生成 → 转入修改并确认。 */
export function LessonPlanGenerateCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const start = useStartNode(nodeRun?.id ?? "");

  if (isPending || !nodeRun) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const confirmUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan-confirm`;
  const canStart = status === "ready" || status === "draft" || status === "failed" || status === "stale";

  const startGeneration = () =>
    start.mutate(undefined, {
      onSuccess: () => toast({ tone: "info", title: "开始生成教案", description: "通常需要一分钟左右。" }),
      onError: (error) => {
        const message = error instanceof AppError ? error.message : "请稍后重试。";
        toast({ tone: "danger", title: "无法开始", description: message });
      },
    });

  return (
    <StepScaffold
      title="生成教案"
      description="教案结构由学校内容规范决定；生成前可以查看和修改完整生成指令。"
      status={status}
      primaryAction={
        canStart ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            {detail?.versions.length ? "重新生成教案" : "开始生成教案"}
          </Button>
        ) : status === "review_required" || status === "approved" ? (
          <Button asChild>
            <Link to={confirmUrl}>
              去修改并确认
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        ) : null
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在生成教案" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成过程中出现问题。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : (
        <div className="mx-auto max-w-3xl space-y-5">
          {status === "review_required" || status === "approved" ? (
            <div className="rounded-lg border border-success-200 bg-success-50 p-4 text-sm text-ink">
              {status === "approved" ? "教案已批准。" : "教案已生成，等待你修改并确认。"}
              <Link to={confirmUrl} className="ml-2 font-medium text-brand-600 hover:underline">
                打开教案
              </Link>
            </div>
          ) : null}
          <PromptSection nodeRunId={nodeRun.id} defaultOpen={canStart} />
          {status === "not_ready" ? (
            <p className="rounded-lg border border-dashed border-line bg-surface-soft p-6 text-center text-sm text-ink-muted">
              等待前置步骤完成（课时划分批准后可生成教案）。
            </p>
          ) : null}
        </div>
      )}
    </StepScaffold>
  );
}
