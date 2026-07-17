import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Play, Sparkles } from "lucide-react";
import { useNodeRunDetail, useNodeResults, useStartNode } from "@/features/node-runs";
import { usePptStyleContract } from "@/features/ppt";
import { PromptSection } from "@/features/prompt-editing";
import { SaveToProjectDialog } from "@/features/save-to-project";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { CandidateGallery, FailedPanel, RunningPanel, StepScaffold } from "../parts";

/**
 * 设计封面：封面是全套 PPT 的画面风格来源（PPT_PRODUCTION 封面门禁）。
 * 采用封面 = 保存到 ppt.cover.main_visual 槽位 → 系统提炼画面风格。
 */
export function PptCoverCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const { data: results } = useNodeResults(nodeRun?.id ?? null, "cover");
  const { data: styleContract } = usePptStyleContract(lessonId);
  const start = useStartNode(nodeRun?.id ?? "");
  const [savingResultId, setSavingResultId] = useState<string | null>(null);

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const bodyUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/ppt-body`;
  const candidates = (results ?? []).filter((r) => r.review_state !== "discarded");

  const startGeneration = () =>
    start.mutate(undefined, {
      onSuccess: () => toast({ tone: "info", title: "正在设计封面", description: "会生成多个候选供你挑选。" }),
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title="设计封面"
      description="封面确定后，正文页面会沿用同一套画面风格。"
      status={status}
      primaryAction={
        status === "approved" ? (
          <Button asChild>
            <Link to={bodyUrl}>
              去制作正文
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        ) : status === "ready" || status === "failed" ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            生成封面候选
          </Button>
        ) : undefined
      }
      secondaryActions={
        status === "review_required" ? (
          <Button variant="outline" onClick={startGeneration} loading={start.isPending} loadingText="正在生成…">
            换一批候选
          </Button>
        ) : undefined
      }
    >
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在设计封面候选" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成失败。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : status === "not_ready" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          先完成「安排页面」，再设计封面。
        </p>
      ) : (
        <div className="mx-auto max-w-4xl space-y-5">
          {status === "approved" && styleContract ? (
            <div className="flex items-start gap-3 rounded-lg border border-success-200 bg-success-50 p-4">
              <Sparkles className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
              <div className="text-sm">
                <p className="font-medium text-ink-strong">封面已确定，画面风格已生效</p>
                <p className="mt-0.5 leading-relaxed text-ink">{styleContract.summary}</p>
              </div>
              {styleContract.cover_preview_url ? (
                <img
                  src={styleContract.cover_preview_url}
                  alt="已采用的封面"
                  className="ml-auto h-20 w-32 shrink-0 rounded-md object-cover"
                />
              ) : null}
            </div>
          ) : null}
          <CandidateGallery
            results={candidates}
            emptyHint="点击「生成封面候选」开始。会生成 2–4 个风格候选。"
            renderActions={(result) =>
              result.review_state === "adopted" ? (
                <Button size="sm" disabled variant="secondary">
                  已采用
                </Button>
              ) : (
                <Button size="sm" onClick={() => setSavingResultId(result.id)}>
                  采用这个封面
                </Button>
              )
            }
          />
          {status !== "approved" ? <PromptSection nodeRunId={nodeRun.id} /> : null}
        </div>
      )}
      <SaveToProjectDialog
        open={Boolean(savingResultId)}
        onOpenChange={(open) => !open && setSavingResultId(null)}
        resultId={savingResultId}
        defaultProjectId={projectId}
        defaultSlotKey="ppt.cover.main_visual"
        slotLabel="本课时 PPT 封面主视觉"
        lockTarget
        onSaved={() =>
          toast({
            tone: "success",
            title: "封面已确定",
            description: "画面风格已提炼，正文页面将沿用同一风格。",
          })
        }
      />
    </StepScaffold>
  );
}
