import { Play } from "lucide-react";
import { useNodeRunDetail, useNodeResults, useStartNode } from "@/features/node-runs";
import { useVideoProject } from "@/features/video";
import { PromptSection } from "@/features/prompt-editing";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { CandidateGallery, FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";
import { useSaveToProject } from "@/features/save-to-project";

/**
 * 确定画面风格：视觉母图 + 画面风格约定（视频链路的 StyleContract）。
 * 采用母图 = 保存到 video.style.master 槽位。
 */
export function VideoStyleCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const { data: results } = useNodeResults(nodeRun?.id ?? null, "style_master");
  const { data: videoProject } = useVideoProject(lessonId);
  const start = useStartNode(nodeRun?.id ?? "");
  const save = useSaveToProject();

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const styleContract = videoProject?.style_contract as
    | { summary?: string; rules?: Record<string, string> }
    | null
    | undefined;

  const startGeneration = () =>
    start.mutate(undefined, {
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title="确定画面风格"
      description="生成视觉母图并确认整支视频的画面风格；后续镜头图片都会沿用。"
      status={status}
      primaryAction={
        status === "ready" || status === "failed" ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            生成视觉母图
          </Button>
        ) : undefined
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在生成视觉母图" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成失败。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : status === "not_ready" || status === "disabled" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          先完成「安排故事镜头」，再确定画面风格。
        </p>
      ) : (
        <div className="mx-auto max-w-4xl space-y-5">
          {styleContract?.summary ? (
            <div className="rounded-lg border border-success-200 bg-success-50 p-4 text-sm">
              <p className="font-medium text-ink-strong">画面风格已确定</p>
              <p className="mt-0.5 leading-relaxed text-ink">{styleContract.summary}</p>
              {styleContract.rules ? (
                <dl className="mt-2 grid gap-x-6 gap-y-1 text-xs text-ink-muted sm:grid-cols-2">
                  {Object.entries(styleContract.rules).map(([key, value]) => (
                    <div key={key} className="flex gap-2">
                      <dt className="shrink-0 font-medium">{STYLE_RULE_LABELS[key] ?? key}</dt>
                      <dd>{value}</dd>
                    </div>
                  ))}
                </dl>
              ) : null}
            </div>
          ) : null}
          <CandidateGallery
            results={(results ?? []).filter((r) => r.review_state !== "discarded")}
            emptyHint="点击「生成视觉母图」开始。"
            renderActions={(result) =>
              result.review_state === "adopted" ? (
                <Button size="sm" disabled variant="secondary">
                  已采用
                </Button>
              ) : (
                <Button
                  size="sm"
                  loading={save.isPending}
                  onClick={() =>
                    save.mutate(
                      {
                        resultId: result.id,
                        projectId,
                        slotKey: "video.style.master",
                        replaceMode: "replace_active",
                      },
                      {
                        onSuccess: () =>
                          toast({ tone: "success", title: "母图已采用", description: "画面风格已生效。" }),
                        onError: (error) => toast({ tone: "danger", title: "采用失败", description: error.message }),
                      },
                    )
                  }
                >
                  就用这种风格
                </Button>
              )
            }
          />
          <PromptSection nodeRunId={nodeRun.id} />
        </div>
      )}
    </StepScaffold>
  );
}

const STYLE_RULE_LABELS: Record<string, string> = {
  medium: "画面材质",
  palette: "色彩",
  lighting: "光线",
  composition: "构图",
  forbidden: "避免",
};
