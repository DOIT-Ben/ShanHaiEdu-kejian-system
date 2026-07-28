import { FileCheck2, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import {
  LessonPlanDocument,
  LessonPlanDraftEditor,
  LessonPlanSectionNavigation,
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

  const reviewStatus = submittedVersionId ? (
    <div className="mt-5 border-t border-[var(--sh-line-subtle)] pt-5">
      <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">质量检查</p>
      <Button
        className="mt-3 w-full"
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
        {qualityPending ? "正在检查" : qualityPassed ? "检查已通过" : "运行质量检查"}
      </Button>
      <p
        className={`mt-3 flex items-start gap-2 text-sm leading-6 ${
          currentQualityReport?.conclusion === "failed"
            ? "text-[var(--sh-danger-strong)]"
            : "text-[var(--sh-ink-muted)]"
        }`}
        role="status"
      >
        <FileCheck2 aria-hidden="true" className="mt-1 size-4 shrink-0" />
        <span>
          {approved
            ? "当前教案已经批准"
            : qualityPassed
              ? "检查通过，可以批准当前版本"
              : currentQualityReport?.conclusion === "failed"
                ? "检查未通过，请修改后重新提交"
                : qualityPending
                  ? "正在检查当前提交版本"
                  : "当前版本尚未检查"}
        </span>
      </p>
    </div>
  ) : (
    <p className="mt-4 text-sm leading-6 text-[var(--sh-ink-muted)]">提交草稿后可运行质量检查。</p>
  );

  return (
    <div className="mt-4 space-y-4">
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
        <ArtifactWorkbench
          artifact={artifact}
          busyAction={busyAction}
          conflictMessage={
            actionError
              ? runtimeErrorMessage(actionError, "当前操作没有完成，请刷新后重试。")
              : undefined
          }
          contentNavigation={<LessonPlanSectionNavigation />}
          draftEditor={
            draftContent && lessonPlanContentReady(draftContent) ? (
              <LessonPlanDraftEditor content={draftContent} onChange={setDraftContent} />
            ) : undefined
          }
          onApprove={qualityPassed ? () => approvalMutation.mutate() : undefined}
          onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
          onSubmit={() => submitMutation.mutate()}
          reviewStatus={reviewStatus}
          reviewUnavailableMessage="当前提交版本正文不完整，暂时不能批准。"
          submittedVersionPreview={
            submittedContent && lessonPlanContentReady(submittedContent) ? (
              <LessonPlanDocument content={submittedContent} />
            ) : undefined
          }
          title="十二部分教案"
          variant="document"
          writeDisabled={!writeReady || !etag || qualityPending || submittedVersionAwaitingRefresh}
        />
      ) : (
        <section className="grid items-start border-y border-[var(--sh-line-default)] bg-[var(--sh-line-subtle)] xl:grid-cols-[190px_minmax(0,1fr)_280px]">
          <aside className="order-3 bg-[var(--sh-surface-base)] p-4 xl:order-1">
            <LessonPlanSectionNavigation disabled />
          </aside>
          <div className="order-1 min-w-0 border-y border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)] px-5 py-7 md:px-8 xl:order-2 xl:border-x xl:border-y-0">
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">教案正文</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--sh-ink-strong)]">
              生成十二部分教案
            </h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--sh-ink-muted)]">
              系统将基于当前课时范围生成可编辑教案。
            </p>
            <label className="mt-6 block text-sm font-medium text-[var(--sh-ink-default)]">
              补充要求（可选）
              <textarea
                className="mt-2 min-h-28 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] p-3 text-sm leading-6 outline-none transition-[border-color,box-shadow] duration-[var(--sh-duration-fast)] focus:border-[var(--sh-brand-500)] focus:shadow-[var(--sh-shadow-focus)] motion-reduce:transition-none"
                maxLength={6000}
                onChange={(event) => setRevision(event.target.value)}
                placeholder="例如：增加一次小组讨论，重点呈现概念形成过程"
                value={revision}
              />
            </label>
            <Button
              className="mt-5"
              disabled={!writeReady || generationMutation.isPending || jobLive}
              onClick={() => generationMutation.mutate(revision)}
            >
              <RefreshCw aria-hidden="true" />
              {generationMutation.isPending ? "正在启动" : "生成十二部分教案"}
            </Button>
            {!writeReady ? (
              <p className="mt-3 text-sm text-[var(--sh-warning-strong)]" role="status">
                当前会话只能查看，刷新或重新登录后再执行写操作。
              </p>
            ) : null}
            {generationError ? (
              <p className="mt-3 text-sm text-[var(--sh-danger-strong)]" role="alert">
                {runtimeErrorMessage(generationError, "教案生成没有启动，请刷新状态后重试。")}
              </p>
            ) : null}
          </div>
          <aside className="order-2 bg-[var(--sh-surface-elevated)] p-5 xl:order-3">
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">当前状态</p>
            <h2 className="mt-2 font-semibold text-[var(--sh-ink-strong)]">尚未生成</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              当前课时还没有教案正文。
            </p>
          </aside>
        </section>
      )}
    </div>
  );
}
