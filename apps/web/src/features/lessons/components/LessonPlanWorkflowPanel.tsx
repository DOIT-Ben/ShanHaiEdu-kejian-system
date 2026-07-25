import { FileCheck2, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import {
  LessonPlanDocument,
  LessonPlanDraftEditor,
  lessonPlanContentReady,
} from "@/features/lessons/components/LessonPlanDocument";
import {
  useLessonPlanApprovalMutation,
  useLessonPlanArtifactRuntime,
  useLessonPlanGenerationMutation,
  useLessonPlanJobRuntime,
  useLessonPlanQualityMutation,
  useSaveLessonPlanDraftMutation,
  useSubmitLessonPlanDraftMutation,
} from "@/features/lessons/hooks/useLessonPlanWorkflow";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

function contentRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function LessonPlanWorkflowPanel({
  lessonId,
  projectId,
}: {
  lessonId: string;
  projectId: string;
}) {
  const [draftContent, setDraftContent] = useState<Record<string, unknown>>();
  const [revision, setRevision] = useState("");
  const artifactRuntime = useLessonPlanArtifactRuntime(projectId, lessonId);
  const jobRuntime = useLessonPlanJobRuntime(projectId, lessonId);
  const { artifact, etag, qualityReport, refetchArtifact } = artifactRuntime;
  const generationMutation = useLessonPlanGenerationMutation({
    lessonId,
    onStarted: jobRuntime.setStartedJobId,
  });
  const saveMutation = useSaveLessonPlanDraftMutation({ artifact, etag, refetchArtifact });
  const submitMutation = useSubmitLessonPlanDraftMutation({ artifact, etag, refetchArtifact });
  const submittedVersionId = artifact?.current_submitted_version?.id;
  const submittedVersionAwaitingRefresh = Boolean(
    submitMutation.isPending ||
    (submitMutation.data && submitMutation.data.id !== submittedVersionId),
  );
  const currentQualityReport =
    qualityReport?.artifact_version_id === submittedVersionId ? qualityReport : undefined;
  const qualityPassed = currentQualityReport?.conclusion === "passed";
  const qualityMutation = useLessonPlanQualityMutation({
    artifact,
    etag,
    lessonId,
    onRequested: artifactRuntime.setQualityPendingVersionId,
    refetchArtifact,
  });
  const approvalMutation = useLessonPlanApprovalMutation({
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

  const writeReady = isCsrfTokenAvailable();
  const jobLive = Boolean(
    jobRuntime.job && !["succeeded", "failed", "cancelled"].includes(jobRuntime.job.status),
  );
  const generationError = generationMutation.error;
  const actionError =
    saveMutation.error ?? submitMutation.error ?? qualityMutation.error ?? approvalMutation.error;
  const busyAction = saveMutation.isPending
    ? "save"
    : submitMutation.isPending
      ? "submit"
      : approvalMutation.isPending
        ? "approve"
        : undefined;
  const submittedContent = contentRecord(artifact?.current_submitted_version?.content);
  const qualityPending =
    qualityMutation.isPending || artifactRuntime.qualityPendingVersionId === submittedVersionId;
  const approved =
    artifact?.status === "approved" &&
    artifact.current_approved_version?.id === artifactRuntime.latestApproval?.artifact_version_id &&
    artifactRuntime.latestApproval?.action === "approve";

  return (
    <div className="mt-5 space-y-5">
      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">十二部分教案</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              {artifact ? "教案已生成，可继续编辑和提交。" : "准备好后开始生成本课时教案。"}
            </p>
          </div>
          <Button
            disabled={
              !writeReady || generationMutation.isPending || jobLive || artifact !== undefined
            }
            onClick={() => generationMutation.mutate(revision)}
          >
            <RefreshCw aria-hidden="true" />
            {artifact ? "教案已生成" : "生成十二部分教案"}
          </Button>
        </div>
        {!artifact ? (
          <label className="mt-4 block text-sm font-medium text-[var(--sh-ink-default)]">
            本次生成要求
            <textarea
              className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-3 leading-6"
              maxLength={6000}
              onChange={(event) => setRevision(event.target.value)}
              placeholder="可选：填写本课时需要重点体现的教学安排"
              value={revision}
            />
          </label>
        ) : null}
        {!writeReady ? (
          <p className="mt-3 text-sm text-[var(--sh-warning)]" role="status">
            当前会话只能查看，刷新或重新登录后再执行写操作。
          </p>
        ) : null}
        {generationError ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {runtimeErrorMessage(generationError, "教案生成没有启动，请刷新状态后重试。")}
          </p>
        ) : null}
      </section>

      {jobRuntime.job || jobRuntime.jobsQuery.isLoading || jobRuntime.jobsQuery.error ? (
        <GenerationJobPanel
          errorMessage={
            jobRuntime.jobsQuery.error || jobRuntime.jobQuery.error
              ? runtimeErrorMessage(
                  jobRuntime.jobsQuery.error ?? jobRuntime.jobQuery.error,
                  "教案任务状态暂时无法读取。",
                )
              : undefined
          }
          job={jobRuntime.job}
          loading={jobRuntime.jobsQuery.isLoading || jobRuntime.jobQuery.isFetching}
          onRefresh={() => void jobRuntime.jobQuery.refetch()}
          title="教案生成进度"
        />
      ) : null}

      {artifactRuntime.aggregateQuery.isLoading ||
      (artifactRuntime.aggregateQuery.data?.artifact && artifactRuntime.detailQuery.isLoading) ? (
        <div
          className="h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
          role="status"
        >
          <span className="sr-only">正在读取十二部分教案</span>
        </div>
      ) : artifactRuntime.aggregateQuery.error || artifactRuntime.detailQuery.error ? (
        <p className="text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(
            artifactRuntime.aggregateQuery.error ?? artifactRuntime.detailQuery.error,
            "十二部分教案暂时无法读取。",
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
              draftContent && lessonPlanContentReady(draftContent) ? (
                <LessonPlanDraftEditor content={draftContent} onChange={setDraftContent} />
              ) : undefined
            }
            onApprove={qualityPassed ? () => approvalMutation.mutate() : undefined}
            onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
            onSubmit={() => submitMutation.mutate()}
            reviewUnavailableMessage="当前提交版本正文不完整，暂时不能批准。"
            submittedVersionPreview={
              submittedContent && lessonPlanContentReady(submittedContent) ? (
                <div className="mt-4 max-h-96 overflow-y-auto border-y border-[var(--sh-line-subtle)] py-4">
                  <LessonPlanDocument content={submittedContent} />
                </div>
              ) : undefined
            }
            title="十二部分教案"
            writeDisabled={
              !writeReady || !etag || qualityPending || submittedVersionAwaitingRefresh
            }
          />

          {submittedVersionId ? (
            <section className="border-t border-[var(--sh-line-subtle)] pt-5">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  disabled={
                    !writeReady ||
                    submittedVersionAwaitingRefresh ||
                    qualityPending ||
                    qualityPassed ||
                    approved
                  }
                  onClick={() => qualityMutation.mutate(submittedVersionId)}
                  variant="secondary"
                >
                  <ShieldCheck aria-hidden="true" />
                  {qualityPending ? "正在检查" : qualityPassed ? "质量检查已通过" : "运行质量检查"}
                </Button>
                <p
                  className={`flex items-center gap-2 text-sm ${
                    currentQualityReport?.conclusion === "failed"
                      ? "text-[var(--sh-danger)]"
                      : "text-[var(--sh-ink-muted)]"
                  }`}
                  role="status"
                >
                  <FileCheck2 aria-hidden="true" className="size-4" />
                  {approved
                    ? "当前教案已经批准"
                    : qualityPassed
                      ? "检查通过，可以批准当前版本"
                      : currentQualityReport?.conclusion === "failed"
                        ? "检查未通过，请修改后重新提交"
                        : qualityPending
                          ? "正在检查当前提交版本"
                          : "提交后运行质量检查"}
                </p>
              </div>
            </section>
          ) : null}
        </>
      ) : (
        <p className="py-8 text-center text-sm text-[var(--sh-ink-muted)]">
          生成完成后，十二部分教案会显示在这里。
        </p>
      )}
    </div>
  );
}
