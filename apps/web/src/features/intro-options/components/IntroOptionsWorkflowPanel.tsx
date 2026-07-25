import { RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import {
  useArtifactApprovalMutation,
  useArtifactQualityMutation,
} from "@/features/artifacts/hooks/useArtifactReviewMutations";
import { ArtifactQualityStatus } from "@/features/artifacts/components/ArtifactQualityStatus";
import { IntroOptionSet } from "@/features/intro-options/components/IntroOptionSet";
import {
  useIntroOptionsGenerationMutation,
  useIntroOptionsJobRuntime,
  useIntroOptionsRuntime,
  useIntroOptionSelectionMutation,
} from "@/features/intro-options/hooks/useIntroOptionsWorkflow";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

export function IntroOptionsWorkflowPanel({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}) {
  const [qualityRequestedVersionId, setQualityRequestedVersionId] = useState<string>();
  const { data, error, missing, query: optionsQuery } = useIntroOptionsRuntime(lessonId);
  const { refetch: refetchOptions } = optionsQuery;
  const { job, jobQuery, jobsKey, jobsQuery, setStartedJobId, workflowQuery } =
    useIntroOptionsJobRuntime(projectId, lessonId);
  const generationMutation = useIntroOptionsGenerationMutation({
    jobsKey,
    lessonId,
    onStarted: setStartedJobId,
  });
  const pendingVersion = data?.pending_version;
  const displayVersion = data?.display_version;
  const qualityMutation = useArtifactQualityMutation({
    artifactVersionId: pendingVersion?.artifact_version_id,
    missingVersionError: "INTRO_OPTION_VERSION_MISSING",
    onRequested: setQualityRequestedVersionId,
  });
  const approvalMutation = useArtifactApprovalMutation({
    artifactVersionId: pendingVersion?.artifact_version_id,
    comment: "三类九套课堂导入方案已审阅确认",
    missingVersionError: "INTRO_OPTION_VERSION_MISSING",
    refetchArtifact: refetchOptions,
  });
  const selectionMutation = useIntroOptionSelectionMutation({
    lessonId,
    refetchOptions,
  });

  useEffect(() => {
    if (job?.status === "succeeded") void refetchOptions();
  }, [job?.id, job?.status, refetchOptions]);

  const writeReady = isCsrfTokenAvailable();
  const jobError = jobsQuery.error ?? workflowQuery.error ?? jobQuery.error;
  const reviewError = qualityMutation.error ?? approvalMutation.error;
  const hasVersion = Boolean(pendingVersion || displayVersion);
  const generationBusy = generationMutation.isPending || Boolean(job && job.status === "running");
  const reviewBusy = qualityMutation.isPending || approvalMutation.isPending;
  const qualityAccepted =
    qualityRequestedVersionId === pendingVersion?.artifact_version_id
      ? qualityMutation.data
      : undefined;

  return (
    <div className="mt-5 space-y-5">
      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">三类九套课堂导入</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              {hasVersion ? "当前方案来自已保存的正式版本。" : "尚未生成当前课时的导入方案。"}
            </p>
          </div>
          <Button
            disabled={!writeReady || generationBusy}
            loading={generationMutation.isPending}
            onClick={() => generationMutation.mutate()}
          >
            <RefreshCw aria-hidden="true" />
            {hasVersion ? "重新生成三类九套" : "生成三类九套"}
          </Button>
        </div>
        {!writeReady ? (
          <p className="mt-3 text-sm text-[var(--sh-warning)]" role="status">
            当前会话只能查看导入方案，无法执行写操作。
          </p>
        ) : null}
        {generationMutation.error ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {runtimeErrorMessage(
              generationMutation.error,
              "三类九套生成任务没有启动，请刷新正式状态后重试。",
            )}
          </p>
        ) : null}
        {job || jobsQuery.isLoading || jobError ? (
          <div className="mt-4">
            <GenerationJobPanel
              errorMessage={
                jobError
                  ? runtimeErrorMessage(jobError, "导入方案任务暂时无法从正式状态恢复。")
                  : undefined
              }
              job={job}
              loading={jobsQuery.isLoading || jobQuery.isFetching}
              onRefresh={() => void jobQuery.refetch()}
            />
          </div>
        ) : null}
      </section>

      {optionsQuery.isLoading ? (
        <div
          className="h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
          role="status"
        >
          <span className="sr-only">正在读取三类九套</span>
        </div>
      ) : error ? (
        <p className="text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(error, "三类九套暂时无法读取。")}
        </p>
      ) : null}

      {pendingVersion ? (
        <section className="border-t border-[var(--sh-line-subtle)] pt-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-[var(--sh-ink-strong)]">待确认三类九套</h2>
              <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                当前待确认版本：{pendingVersion.version_no}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={!writeReady || reviewBusy}
                onClick={() => qualityMutation.mutate()}
                variant="secondary"
              >
                <ShieldCheck aria-hidden="true" />
                运行导入方案质量校验
              </Button>
              <Button
                disabled={!writeReady || reviewBusy}
                onClick={() => approvalMutation.mutate()}
              >
                批准三类九套
              </Button>
            </div>
          </div>
          <div className="mb-4">
            <ArtifactQualityStatus
              accepted={qualityAccepted}
              nodeRuns={workflowQuery.data?.node_runs}
              subject="导入方案"
            />
          </div>
          {reviewError ? (
            <p className="mb-4 text-sm text-[var(--sh-danger)]" role="alert">
              {runtimeErrorMessage(reviewError, "当前导入方案审核操作没有完成。")}
            </p>
          ) : null}
          <IntroOptionSet
            onSelect={() => undefined}
            selection={data.current_selection}
            version={pendingVersion}
            writeDisabled
          />
        </section>
      ) : null}

      {displayVersion ? (
        <section className="border-t border-[var(--sh-line-subtle)] pt-5">
          <div className="mb-4">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">
              已批准版本 {displayVersion.version_no}
            </h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              知识点：{displayVersion.option_set.knowledge_point}
            </p>
          </div>
          {selectionMutation.error ? (
            <p className="mb-4 text-sm text-[var(--sh-danger)]" role="alert">
              {runtimeErrorMessage(selectionMutation.error, "当前导入方案没有选用成功。")}
            </p>
          ) : null}
          <IntroOptionSet
            onSelect={(option) =>
              selectionMutation.mutate({
                artifactVersionId: displayVersion.artifact_version_id,
                optionKey: option.option_key,
              })
            }
            selection={data.current_selection}
            version={displayVersion}
            writeDisabled={!writeReady || selectionMutation.isPending}
          />
        </section>
      ) : null}

      {missing && !job ? (
        <p className="text-sm text-[var(--sh-ink-muted)]">当前课时还没有导入方案版本。</p>
      ) : null}
    </div>
  );
}
