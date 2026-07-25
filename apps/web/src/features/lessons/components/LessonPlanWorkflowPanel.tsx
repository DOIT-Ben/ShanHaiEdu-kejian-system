import { RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import { ArtifactQualityStatus } from "@/features/artifacts/components/ArtifactQualityStatus";
import {
  useArtifactApprovalMutation,
  useArtifactQualityMutation,
} from "@/features/artifacts/hooks/useArtifactReviewMutations";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import {
  LessonPlanDocument,
  LessonPlanDraftEditor,
  lessonPlanContentReady,
} from "@/features/lessons/components/LessonPlanDocument";
import {
  useLessonPlanArtifactRuntime,
  useLessonPlanGenerationMutation,
  useLessonPlanJobRuntime,
  useSaveLessonPlanDraftMutation,
  useSubmitLessonPlanDraftMutation,
} from "@/features/lessons/hooks/useLessonPlanWorkflow";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button, buttonVariants } from "@/shared/ui/Button";

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
  const [qualityRequestedVersionId, setQualityRequestedVersionId] = useState<string>();
  const { artifact, detailKey, detailQuery, etag, listQuery } = useLessonPlanArtifactRuntime(
    projectId,
    lessonId,
  );
  const { job, jobQuery, jobsKey, jobsQuery, setStartedJobId, workflowQuery } =
    useLessonPlanJobRuntime(projectId, lessonId);
  const generationMutation = useLessonPlanGenerationMutation({
    jobsKey,
    lessonId,
    onStarted: setStartedJobId,
  });
  const saveMutation = useSaveLessonPlanDraftMutation({ artifact, detailKey, etag });
  const submitMutation = useSubmitLessonPlanDraftMutation({
    artifact,
    etag,
    refetchArtifact: detailQuery.refetch,
  });
  const qualityMutation = useArtifactQualityMutation({
    artifactVersionId: artifact?.current_submitted_version?.id,
    missingVersionError: "LESSON_PLAN_VERSION_MISSING",
    onRequested: setQualityRequestedVersionId,
  });
  const approvalMutation = useArtifactApprovalMutation({
    artifactVersionId: artifact?.current_submitted_version?.id,
    comment: "十二部分教案已审阅确认",
    missingVersionError: "LESSON_PLAN_VERSION_MISSING",
    refetchArtifact: detailQuery.refetch,
  });

  useEffect(() => {
    setDraftContent(contentRecord(artifact?.current_draft?.content));
  }, [
    artifact?.current_draft?.content,
    artifact?.current_draft?.id,
    artifact?.current_draft?.lock_version,
  ]);

  const writeReady = isCsrfTokenAvailable();
  const actionError =
    saveMutation.error ?? submitMutation.error ?? qualityMutation.error ?? approvalMutation.error;
  const artifactError = listQuery.error ?? detailQuery.error;
  const generationError = generationMutation.error;
  const jobError = jobsQuery.error ?? workflowQuery.error ?? jobQuery.error;
  const busyAction = saveMutation.isPending
    ? "save"
    : submitMutation.isPending
      ? "submit"
      : approvalMutation.isPending
        ? "approve"
        : undefined;
  const submittedContent = contentRecord(artifact?.current_submitted_version?.content);
  const approved = artifact?.status === "approved" && artifact.current_approved_version !== null;
  const actionPending = Boolean(busyAction || qualityMutation.isPending);
  const qualityAccepted =
    qualityRequestedVersionId === artifact?.current_submitted_version?.id
      ? qualityMutation.data
      : undefined;

  return (
    <div className="mt-5 space-y-5">
      <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">十二部分教案生成</h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              任务由后台 Worker 执行，刷新后仍从正式 Job 恢复。
            </p>
          </div>
          <Button
            disabled={
              !writeReady ||
              generationMutation.isPending ||
              Boolean(job && job.status === "running")
            }
            onClick={() => generationMutation.mutate(revision)}
          >
            <RefreshCw aria-hidden="true" />
            {artifact ? "局部重生成" : "生成十二部分教案"}
          </Button>
        </div>
        <label className="mt-4 block text-sm font-medium text-[var(--sh-ink-default)]">
          本次生成要求
          <textarea
            className="mt-2 min-h-24 w-full resize-y rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] p-3 leading-6"
            maxLength={6000}
            onChange={(event) => setRevision(event.target.value)}
            value={revision}
          />
        </label>
        {!writeReady ? (
          <p className="mt-3 text-sm text-[var(--sh-warning)]" role="status">
            当前会话只能查看教案，无法启动或提交写操作。
          </p>
        ) : null}
        {generationError ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {runtimeErrorMessage(generationError, "教案生成任务没有启动，请刷新正式状态后重试。")}
          </p>
        ) : null}
        {job || jobsQuery.isLoading || jobError ? (
          <div className="mt-4">
            <GenerationJobPanel
              errorMessage={
                jobError
                  ? runtimeErrorMessage(jobError, "教案任务暂时无法从正式状态恢复。")
                  : undefined
              }
              job={job}
              loading={jobsQuery.isLoading || jobQuery.isFetching}
              onRefresh={() => void jobQuery.refetch()}
            />
          </div>
        ) : null}
      </section>

      {listQuery.isLoading || (listQuery.data?.items.length && detailQuery.isLoading) ? (
        <div
          className="h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
          role="status"
        >
          <span className="sr-only">正在读取十二部分教案</span>
        </div>
      ) : artifactError ? (
        <p className="text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(artifactError, "十二部分教案暂时无法读取。")}
        </p>
      ) : artifact ? (
        <>
          <ArtifactWorkbench
            artifact={artifact}
            busyAction={busyAction}
            conflictMessage={
              actionError
                ? runtimeErrorMessage(actionError, "当前教案操作没有完成，请刷新后重试。")
                : undefined
            }
            draftEditor={
              draftContent && lessonPlanContentReady(draftContent) ? (
                <LessonPlanDraftEditor content={draftContent} onChange={setDraftContent} />
              ) : undefined
            }
            onApprove={() => approvalMutation.mutate()}
            onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
            onSubmit={() => submitMutation.mutate()}
            submittedVersionPreview={
              submittedContent && lessonPlanContentReady(submittedContent) ? (
                <div className="mt-4">
                  <LessonPlanDocument content={submittedContent} />
                </div>
              ) : undefined
            }
            title="十二部分教案"
            writeDisabled={!writeReady || !etag || actionPending}
          />
          {artifact.current_submitted_version ? (
            <section className="border-t border-[var(--sh-line-subtle)] pt-5">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  disabled={!writeReady || actionPending || !submittedContent}
                  onClick={() => qualityMutation.mutate()}
                  variant="secondary"
                >
                  <ShieldCheck aria-hidden="true" />
                  运行教案质量校验
                </Button>
                <ArtifactQualityStatus
                  accepted={qualityAccepted}
                  nodeRuns={workflowQuery.data?.node_runs}
                  subject="教案"
                />
              </div>
            </section>
          ) : null}
          {approved ? (
            <div className="flex justify-end">
              <Link
                className={buttonVariants({ variant: "primary" })}
                to={`/app/projects/${projectId}/lessons/${lessonId}/work/intro_options`}
              >
                进入课堂导入
              </Link>
            </div>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
