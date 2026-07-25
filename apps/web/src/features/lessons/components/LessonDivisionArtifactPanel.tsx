import { FileCheck2, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { ArtifactWorkbench } from "@/features/artifacts/components/ArtifactWorkbench";
import {
  LessonDivisionDocument,
  LessonDivisionDraftEditor,
  lessonDivisionContentReady,
} from "@/features/lessons/components/LessonDivisionDocument";
import {
  useLessonDivisionApprovalMutation,
  useLessonDivisionQualityMutation,
  useSaveLessonDivisionDraftMutation,
  useSubmitLessonDivisionDraftMutation,
} from "@/features/lessons/hooks/useLessonDivisionWorkflow";
import type { useLessonDivisionArtifactRuntime } from "@/features/lessons/hooks/useLessonDivisionWorkflow";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

function contentRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function LessonDivisionArtifactPanel({
  approved,
  projectId,
  runtime,
}: {
  approved: boolean;
  projectId: string;
  runtime: ReturnType<typeof useLessonDivisionArtifactRuntime>;
}) {
  const [draftContent, setDraftContent] = useState<Record<string, unknown>>();
  const { artifact, etag, qualityReport, refetch } = runtime;
  const saveMutation = useSaveLessonDivisionDraftMutation({ artifact, etag, refetch });
  const submitMutation = useSubmitLessonDivisionDraftMutation({ artifact, etag, refetch });
  const submittedVersionId = artifact?.current_submitted_version?.id;
  const submittedVersionAwaitingRefresh = Boolean(
    submitMutation.isPending ||
    (submitMutation.data && submitMutation.data.id !== submittedVersionId),
  );
  const currentQualityReport =
    qualityReport?.artifact_version_id === submittedVersionId ? qualityReport : undefined;
  const qualityPassed = currentQualityReport?.conclusion === "passed";
  const qualityMutation = useLessonDivisionQualityMutation({
    artifact,
    etag,
    onRequested: runtime.setQualityPendingVersionId,
    projectId,
    refetch,
  });
  const approvalMutation = useLessonDivisionApprovalMutation({
    artifact,
    etag,
    qualityPassed,
    refetch,
  });

  useEffect(() => {
    setDraftContent(contentRecord(artifact?.current_draft?.content));
  }, [
    artifact?.current_draft?.content,
    artifact?.current_draft?.id,
    artifact?.current_draft?.lock_version,
  ]);

  if (
    runtime.aggregateQuery.isLoading ||
    (runtime.aggregateQuery.data?.artifact && runtime.detailQuery.isLoading)
  ) {
    return (
      <div
        className="mt-5 h-64 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
        role="status"
      >
        <span className="sr-only">正在读取课时划分</span>
      </div>
    );
  }
  if (runtime.aggregateQuery.error || runtime.detailQuery.error) {
    return (
      <p className="mt-4 text-sm text-[var(--sh-danger)]" role="alert">
        {runtimeErrorMessage(
          runtime.aggregateQuery.error ?? runtime.detailQuery.error,
          "课时划分暂时无法读取。",
        )}
      </p>
    );
  }
  if (!artifact) {
    return (
      <p className="mt-4 py-6 text-center text-sm text-[var(--sh-ink-muted)]">
        生成完成后，课时划分会显示在这里。
      </p>
    );
  }

  const qualityPending =
    qualityMutation.isPending || runtime.qualityPendingVersionId === submittedVersionId;
  const submittedContent = contentRecord(artifact.current_submitted_version?.content);
  const actionError =
    saveMutation.error ?? submitMutation.error ?? qualityMutation.error ?? approvalMutation.error;
  const busyAction = saveMutation.isPending
    ? "save"
    : submitMutation.isPending
      ? "submit"
      : approvalMutation.isPending
        ? "approve"
        : undefined;
  const writeDisabled =
    !isCsrfTokenAvailable() || !etag || qualityPending || submittedVersionAwaitingRefresh;

  return (
    <div className="mt-5 space-y-5">
      <ArtifactWorkbench
        artifact={artifact}
        busyAction={busyAction}
        conflictMessage={
          actionError
            ? runtimeErrorMessage(actionError, "当前操作没有完成，请刷新后重试。")
            : undefined
        }
        draftEditor={
          draftContent && lessonDivisionContentReady(draftContent) ? (
            <LessonDivisionDraftEditor content={draftContent} onChange={setDraftContent} />
          ) : undefined
        }
        onApprove={qualityPassed ? () => approvalMutation.mutate() : undefined}
        onSaveDraft={draftContent ? () => saveMutation.mutate(draftContent) : undefined}
        onSubmit={() => submitMutation.mutate()}
        reviewUnavailableMessage="当前课时划分正文不完整，暂时不能批准。"
        submittedVersionPreview={
          submittedContent && lessonDivisionContentReady(submittedContent) ? (
            <div className="mt-4 max-h-96 overflow-y-auto border-y border-[var(--sh-line-subtle)] py-4">
              <LessonDivisionDocument content={submittedContent} />
            </div>
          ) : undefined
        }
        title="课时划分"
        writeDisabled={writeDisabled}
      />

      {submittedVersionId ? (
        <div className="flex flex-wrap items-center gap-3 border-t border-[var(--sh-line-subtle)] pt-5">
          <Button
            disabled={
              !isCsrfTokenAvailable() ||
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
              ? "当前课时划分已经批准"
              : qualityPassed
                ? "检查通过，可以批准当前版本"
                : currentQualityReport?.conclusion === "failed"
                  ? "检查未通过，请修改后重新提交"
                  : qualityPending
                    ? "正在检查当前提交版本"
                    : "提交后运行质量检查"}
          </p>
        </div>
      ) : null}
    </div>
  );
}
