import { Link } from "react-router";
import { ArrowRight, Play } from "lucide-react";
import { useNodeRunDetail, useStartNode, useArtifactVersion } from "@/features/node-runs";
import { ApprovalActions } from "@/features/approvals";
import { PromptSection } from "@/features/prompt-editing";
import { Button, Skeleton, toast } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { FailedPanel, RunningPanel, StepScaffold, StaleBanner } from "../parts";

/** 安排页面（PPT 大纲）：每页教学任务清单，确认后进入封面设计。 */
export function PptOutlineCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const start = useStartNode(nodeRun?.id ?? "");
  const versionId = detail?.node_run.current_artifact_version_id ?? null;
  const { data: artifact } = useArtifactVersion(versionId);

  if (isPending || !nodeRun) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = detail?.node_run.status ?? nodeRun.status;
  const coverUrl = `/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`;
  const canStart = status === "ready" || status === "failed";
  const outline = (artifact?.version.content ?? {}) as {
    pages?: { page_key: string; page_type: string; teaching_task: string; content_summary?: string }[];
  };

  const startGeneration = () =>
    start.mutate(undefined, {
      onError: (error) => toast({ tone: "danger", title: "无法开始", description: error.message }),
    });

  return (
    <StepScaffold
      title="安排 PPT 页面"
      description="先确定每一页承担的教学任务，再设计封面与正文。"
      status={status}
      primaryAction={
        canStart ? (
          <Button onClick={startGeneration} loading={start.isPending} loadingText="正在开始…">
            <Play className="size-4" aria-hidden />
            生成页面安排
          </Button>
        ) : status === "review_required" && versionId ? (
          <ApprovalActions
            versionId={versionId}
            nodeRunId={nodeRun.id}
            validationIssues={artifact?.version.validation_issues ?? []}
            approveLabel="确认页面安排"
          />
        ) : status === "approved" ? (
          <Button asChild>
            <Link to={coverUrl}>
              去设计封面
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        ) : null
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={detail?.node_run ?? nodeRun} /> : null}
      {status === "queued" || status === "running" ? (
        <RunningPanel job={detail?.active_job ?? null} label="正在安排页面" />
      ) : status === "failed" ? (
        <FailedPanel
          message={detail?.active_job?.error?.message ?? "生成失败。"}
          onRetry={startGeneration}
          retrying={start.isPending}
        />
      ) : status === "not_ready" ? (
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          教案批准后即可安排 PPT 页面。
        </p>
      ) : (
        <div className="mx-auto max-w-3xl space-y-5">
          {outline.pages && outline.pages.length > 0 ? (
            <ol className="space-y-2.5">
              {outline.pages.map((page, index) => (
                <li
                  key={page.page_key}
                  className="flex items-start gap-3 rounded-lg border border-line-subtle bg-surface p-4"
                >
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-brand-50 text-xs font-semibold text-brand-600">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink-strong">
                      {page.page_type === "cover" ? "封面" : `第 ${index + 1} 页`} · {page.teaching_task}
                    </p>
                    {page.content_summary ? (
                      <p className="mt-0.5 text-sm leading-relaxed text-ink-muted">{page.content_summary}</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
              点击「生成页面安排」，依据已批准的教案生成每页教学任务。
            </p>
          )}
          <PromptSection nodeRunId={nodeRun.id} />
        </div>
      )}
    </StepScaffold>
  );
}
