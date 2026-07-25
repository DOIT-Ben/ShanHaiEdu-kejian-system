import { useEffect, useState } from "react";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { ApprovedIntroOptionSelection } from "@/features/intro-options/components/ApprovedIntroOptionSelection";
import { IntroOptionSetDocument } from "@/features/intro-options/components/IntroOptionSetDocument";
import { IntroOptionsGenerationPanel } from "@/features/intro-options/components/IntroOptionsGenerationPanel";
import { IntroOptionsQualityStatus } from "@/features/intro-options/components/IntroOptionsQualityStatus";
import {
  useIntroOptionSelectionMutation,
  useIntroOptionsApprovalMutation,
  useIntroOptionsArtifactRuntime,
  useIntroOptionsGenerationMutation,
  useIntroOptionsJobRuntime,
  useIntroOptionsQualityMutation,
  useSaveIntroOptionsDraftMutation,
  useSubmitIntroOptionsDraftMutation,
} from "@/features/intro-options/hooks/useIntroOptionsWorkflow";
import { readIntroOptionSet } from "@/features/intro-options/artifactContent";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";

function contentRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function IntroOptionsWorkflowPanel({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}) {
  const [draftContent, setDraftContent] = useState<Record<string, unknown>>();
  const [revision, setRevision] = useState("");
  const artifactRuntime = useIntroOptionsArtifactRuntime(projectId, lessonId);
  const jobRuntime = useIntroOptionsJobRuntime(projectId, lessonId);
  const { artifact, etag, qualityReport, refetchArtifact } = artifactRuntime;
  const generationMutation = useIntroOptionsGenerationMutation({
    lessonId,
    onStarted: jobRuntime.setStartedJobId,
  });
  const saveMutation = useSaveIntroOptionsDraftMutation({ artifact, etag, refetchArtifact });
  const submitMutation = useSubmitIntroOptionsDraftMutation({ artifact, etag, refetchArtifact });
  const submittedVersionId = artifact?.current_submitted_version?.id;
  const submittedVersionAwaitingRefresh = Boolean(
    submitMutation.isPending ||
    (submitMutation.data && submitMutation.data.id !== submittedVersionId),
  );
  const currentQualityReport =
    qualityReport?.artifact_version_id === submittedVersionId ? qualityReport : undefined;
  const qualityPassed = currentQualityReport?.conclusion === "passed";
  const qualityMutation = useIntroOptionsQualityMutation({
    artifact,
    etag,
    lessonId,
    onRequested: artifactRuntime.setQualityPendingVersionId,
    refetchArtifact,
  });
  const approvalMutation = useIntroOptionsApprovalMutation({
    artifact,
    etag,
    qualityPassed,
    refetchArtifact,
  });

  useEffect(() => {
    setDraftContent(contentRecord(artifact?.current_draft?.content));
  }, [
    artifact?.current_draft?.content,
    artifact?.current_draft?.id,
    artifact?.current_draft?.lock_version,
  ]);

  const publicVersion = artifactRuntime.publicQuery.data?.display_version;
  const approvedVersionId = artifact?.current_approved_version?.id;
  const submittedApproved = Boolean(
    submittedVersionId &&
    submittedVersionId === approvedVersionId &&
    artifactRuntime.latestApproval?.artifact_version_id === submittedVersionId &&
    artifactRuntime.latestApproval.action === "approve",
  );
  const selectableVersionId =
    publicVersion?.selectable && publicVersion.artifact_version_id === approvedVersionId
      ? publicVersion.artifact_version_id
      : undefined;
  const selectionMutation = useIntroOptionSelectionMutation({
    lessonId,
    refetchArtifact,
    selectableVersionId,
  });
  const submittedContent = contentRecord(artifact?.current_submitted_version?.content);
  const submittedReady = Boolean(submittedContent && readIntroOptionSet(submittedContent));
  const writeReady = isCsrfTokenAvailable();
  const jobLive = Boolean(
    jobRuntime.job && !["succeeded", "failed", "cancelled"].includes(jobRuntime.job.status),
  );
  const qualityPending =
    qualityMutation.isPending || artifactRuntime.qualityPendingVersionId === submittedVersionId;
  const actionError =
    saveMutation.error ??
    submitMutation.error ??
    qualityMutation.error ??
    approvalMutation.error ??
    selectionMutation.error;
  const busyAction = saveMutation.isPending
    ? "save"
    : submitMutation.isPending
      ? "submit"
      : approvalMutation.isPending
        ? "approve"
        : undefined;

  return (
    <div className="mt-5 space-y-5">
      <IntroOptionsGenerationPanel
        artifactReady={Boolean(artifact)}
        canWrite={writeReady}
        error={generationMutation.error}
        jobLive={jobLive}
        onRevisionChange={setRevision}
        onStart={() => generationMutation.mutate(revision)}
        pending={generationMutation.isPending}
        revision={revision}
      />

      {jobRuntime.job || jobRuntime.jobsQuery.isLoading || jobRuntime.jobsQuery.error ? (
        <GenerationJobPanel
          errorMessage={
            jobRuntime.jobsQuery.error || jobRuntime.jobQuery.error
              ? runtimeErrorMessage(
                  jobRuntime.jobsQuery.error ?? jobRuntime.jobQuery.error,
                  "三类九套任务状态暂时无法读取。",
                )
              : undefined
          }
          job={jobRuntime.job}
          loading={jobRuntime.jobsQuery.isLoading || jobRuntime.jobQuery.isFetching}
          onRefresh={() => void jobRuntime.jobQuery.refetch()}
          title="三类九套生成进度"
        />
      ) : null}

      {artifactRuntime.aggregateQuery.isLoading ||
      (artifactRuntime.aggregateQuery.data?.artifact && artifactRuntime.detailQuery.isLoading) ? (
        <div
          className="h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
          role="status"
        >
          <span className="sr-only">正在读取三类九套</span>
        </div>
      ) : artifactRuntime.aggregateQuery.error || artifactRuntime.detailQuery.error ? (
        <p className="text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(
            artifactRuntime.aggregateQuery.error ?? artifactRuntime.detailQuery.error,
            "三类九套暂时无法读取。",
          )}
        </p>
      ) : artifact ? (
        <>
          <ArtifactWorkbench
            artifact={artifact}
            busyAction={busyAction}
            conflictMessage={
              actionError
                ? runtimeErrorMessage(actionError, "当前操作没有完成，请刷新后重试。")
                : undefined
            }
            draftEditor={
              draftContent && readIntroOptionSet(draftContent) ? (
                <IntroOptionSetDocument
                  content={draftContent}
                  editable
                  onChange={setDraftContent}
                />
              ) : undefined
            }
            onApprove={qualityPassed ? () => approvalMutation.mutate() : undefined}
            onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
            onSubmit={() => submitMutation.mutate()}
            reviewUnavailableMessage="当前提交版本不是完整三类九套，暂时不能批准。"
            submittedVersionPreview={
              submittedReady ? (
                <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
                  当前提交版本包含科普、应用、故事各三套，可在下方核对完整内容。
                </p>
              ) : undefined
            }
            title="三类九套方案"
            writeDisabled={
              !writeReady || !etag || qualityPending || submittedVersionAwaitingRefresh
            }
          />

          {submittedContent && submittedReady ? (
            <section
              className="border-t border-[var(--sh-line-subtle)] pt-5"
              aria-labelledby="intro-submitted-title"
            >
              <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="intro-submitted-title">
                当前提交版本
              </h2>
              <div className="mt-4">
                <IntroOptionSetDocument content={submittedContent} />
              </div>
            </section>
          ) : null}

          {submittedVersionId ? (
            <IntroOptionsQualityStatus
              disabled={
                !writeReady ||
                submittedVersionAwaitingRefresh ||
                qualityPending ||
                qualityPassed ||
                submittedApproved
              }
              failed={currentQualityReport?.conclusion === "failed"}
              onRun={() => qualityMutation.mutate(submittedVersionId)}
              passed={qualityPassed}
              pending={qualityPending}
              submittedApproved={submittedApproved}
            />
          ) : null}

          {approvedVersionId ? (
            <ApprovedIntroOptionSelection
              canSelect={Boolean(selectableVersionId && writeReady)}
              loading={artifactRuntime.publicQuery.isLoading}
              onSelect={(optionKey) => selectionMutation.mutate(optionKey)}
              optionSet={publicVersion?.option_set}
              selectedOptionKey={artifactRuntime.publicQuery.data?.current_selection?.option_key}
              selectingOptionKey={
                selectionMutation.isPending ? selectionMutation.variables : undefined
              }
            />
          ) : null}
        </>
      ) : (
        <p className="py-8 text-center text-sm text-[var(--sh-ink-muted)]">
          生成完成后，三类九套会显示在这里。
        </p>
      )}
    </div>
  );
}
