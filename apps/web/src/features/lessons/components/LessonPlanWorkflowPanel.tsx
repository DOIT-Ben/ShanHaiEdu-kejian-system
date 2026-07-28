import { FileCheck2, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import {
  LessonPlanDocument,
  LessonPlanDraftEditor,
  LessonPlanSectionNavigation,
  lessonPlanContentReady,
  lessonPlanSections,
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
  const completedAction = busyAction
    ? undefined
    : approvalMutation.isSuccess
      ? "approve"
      : submitMutation.isSuccess
        ? "submit"
        : saveMutation.isSuccess
          ? "save"
          : undefined;
  const submittedContent = contentRecord(artifact?.current_submitted_version?.content);
  const qualityPending =
    qualityMutation.isPending || artifactRuntime.qualityPendingVersionId === submittedVersionId;
  const approved =
    artifact?.status === "approved" &&
    artifact.current_approved_version?.id === artifactRuntime.latestApproval?.artifact_version_id &&
    artifactRuntime.latestApproval?.action === "approve";
  const writeDisabledMessage = !writeReady
    ? "当前会话只能查看，刷新或重新登录后再执行写操作。"
    : !etag
      ? "教案版本信息尚未就绪，请刷新后再执行写操作。"
      : undefined;
  const generationSettling = jobRuntime.job?.status === "succeeded";
  const generationFailed = jobRuntime.job?.status === "failed";
  const generationCancelled = jobRuntime.job?.status === "cancelled";
  const generationStarting = generationMutation.isPending;
  const generationHeading = generationStarting
    ? "正在启动教案生成"
    : jobLive
      ? "正在生成教案"
      : generationSettling
        ? "正在载入教案"
        : generationFailed
          ? "教案生成未完成"
          : generationCancelled
            ? "教案生成已取消"
            : "尚未生成";
  const generationDescription = generationStarting
    ? "正在创建生成任务，请稍候。"
    : jobLive
      ? jobRuntime.job?.progress_message || "系统正在生成十二部分教案。"
      : generationSettling
        ? "生成已经完成，正在读取教案正文。"
        : generationFailed
          ? "上一次生成没有完成，可调整补充要求后重试。"
          : generationCancelled
            ? "上一次生成已取消，可重新启动。"
            : "当前课时还没有教案正文。";
  const generationActionLabel = generationStarting
    ? "正在启动"
    : jobLive
      ? jobRuntime.job?.status === "queued"
        ? "等待生成"
        : "正在生成"
      : generationSettling
        ? "正在载入"
        : generationFailed || generationCancelled
          ? "重新生成十二部分教案"
          : "生成十二部分教案";
  const generationStageLabel = generationStarting
    ? "正在启动"
    : jobLive
      ? "进行中"
      : generationSettling
        ? "已生成"
        : generationFailed
          ? "未完成"
          : generationCancelled
            ? "已取消"
            : "待开始";
  const generationPromptHeading = generationStarting
    ? "正在启动十二部分教案"
    : jobLive
      ? "十二部分教案生成中"
      : generationSettling
        ? "正在载入十二部分教案"
        : generationFailed || generationCancelled
          ? "重新生成十二部分教案"
          : "生成十二部分教案";
  const updateDraftContent = (content: Record<string, unknown>) => {
    saveMutation.reset();
    setDraftContent(content);
  };

  const reviewStatus = submittedVersionId ? (
    <div className="mt-5 border-t border-[var(--sh-line-subtle)] pt-5">
      <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">质量检查</p>
      <Button
        className="mt-3 min-h-11 w-full"
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
          completedAction={completedAction}
          conflictMessage={
            actionError
              ? runtimeErrorMessage(actionError, "当前操作没有完成，请刷新后重试。")
              : undefined
          }
          contentNavigation={<LessonPlanSectionNavigation />}
          draftEditor={
            draftContent && lessonPlanContentReady(draftContent) ? (
              <LessonPlanDraftEditor
                content={draftContent}
                idPrefix="lesson-plan-section"
                onChange={updateDraftContent}
              />
            ) : undefined
          }
          onApprove={qualityPassed ? () => approvalMutation.mutate() : undefined}
          onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
          onSubmit={() => submitMutation.mutate()}
          reviewStatus={reviewStatus}
          reviewUnavailableMessage="当前提交版本正文不完整，暂时不能批准。"
          submittedVersionPreview={
            submittedContent && lessonPlanContentReady(submittedContent) ? (
              <LessonPlanDocument
                content={submittedContent}
                idPrefix="lesson-plan-submitted-section"
              />
            ) : undefined
          }
          title="十二部分教案"
          variant="document"
          writeDisabled={!writeReady || !etag || qualityPending || submittedVersionAwaitingRefresh}
          writeDisabledMessage={writeDisabledMessage}
        />
      ) : (
        <section className="grid border-y border-[var(--sh-line-default)] bg-[var(--sh-line-subtle)] xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="order-1 min-w-0 border-b border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)] px-5 py-7 md:px-8 xl:border-b-0 xl:border-r">
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">教案正文</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--sh-ink-strong)]">
              {generationPromptHeading}
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
              className="mt-5 min-h-11"
              disabled={!writeReady || generationStarting || jobLive || generationSettling}
              loading={generationStarting}
              loadingText="正在启动"
              onClick={() => generationMutation.mutate(revision)}
            >
              <RefreshCw aria-hidden="true" />
              {generationActionLabel}
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
            <div className="mt-8 border-t border-[var(--sh-line-subtle)] pt-5">
              <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">十二部分结构</p>
              <ol className="mt-3 grid grid-cols-2 gap-x-5 gap-y-1 sm:grid-cols-3">
                {lessonPlanSections.map(([key, label]) => (
                  <li
                    className="flex min-h-9 items-center text-xs leading-5 text-[var(--sh-ink-muted)]"
                    key={key}
                  >
                    {label}
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <aside className="order-2 self-stretch bg-[var(--sh-surface-elevated)] p-5">
            <p className="text-xs font-semibold text-[var(--sh-ink-faint)]">当前状态</p>
            <h2 className="mt-2 font-semibold text-[var(--sh-ink-strong)]">{generationHeading}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              {generationDescription}
            </p>
            <ol className="mt-5 border-t border-[var(--sh-line-subtle)] pt-3">
              {["生成教案", "编辑草稿", "质量检查", "教师批准"].map((label, index) => (
                <li className="flex min-h-11 items-center gap-3 text-sm" key={label}>
                  <span
                    className={`grid size-6 shrink-0 place-items-center rounded-full border text-xs font-semibold ${index === 0 ? "border-[var(--sh-brand-400)] bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]" : "border-[var(--sh-line-default)] text-[var(--sh-ink-faint)]"}`}
                  >
                    {index + 1}
                  </span>
                  <span
                    className={
                      index === 0
                        ? "font-medium text-[var(--sh-ink-strong)]"
                        : "text-[var(--sh-ink-muted)]"
                    }
                  >
                    {label}
                  </span>
                  <span className="ml-auto text-xs text-[var(--sh-ink-faint)]">
                    {index === 0 ? generationStageLabel : "等待"}
                  </span>
                </li>
              ))}
            </ol>
          </aside>
        </section>
      )}
    </div>
  );
}
