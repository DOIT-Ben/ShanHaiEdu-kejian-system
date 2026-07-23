import type { ReactElement } from "react";
import type { ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type ArtifactWorkbenchProps = {
  artifact: ArtifactDto;
  busyAction?: "approve" | "save" | "submit";
  conflictMessage?: string;
  draftEditor?: ReactElement;
  draftUnavailableMessage?: string;
  onApprove?: (versionId: string) => void;
  onSaveDraft?: () => void;
  onSubmit?: (draftBranch: string) => void;
  reviewUnavailableMessage?: string;
  submittedVersionPreview?: ReactElement;
  title: string;
  writeDisabled?: boolean;
};

function artifactStatus(status: ArtifactDto["status"]): WorkflowStatus {
  if (status === "in_review") return "review_required";
  if (status === "archived") return "disabled";
  return status;
}

export function ArtifactWorkbench({
  artifact,
  busyAction,
  conflictMessage,
  draftEditor,
  draftUnavailableMessage = "草稿正文暂不可查看或编辑，保存和提交已停用。",
  onApprove,
  onSaveDraft,
  onSubmit,
  reviewUnavailableMessage = "待确认版本正文暂不可查看，批准操作已停用。",
  submittedVersionPreview,
  title,
  writeDisabled = false,
}: ArtifactWorkbenchProps) {
  const draftBranch = artifact.current_draft?.draft_branch ?? "main";
  const submitted = artifact.current_submitted_version;
  const approved = artifact.current_approved_version;
  const writePending = busyAction !== undefined;
  const submittedIsApproved = Boolean(submitted && approved && submitted.id === approved.id);
  const draftContentReady = draftEditor !== undefined;
  const reviewContentReady = submittedVersionPreview !== undefined;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
      <section className="min-w-0 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">{title}</h2>
          <StatusBadge
            label={artifact.status === "archived" ? "已归档" : undefined}
            status={artifactStatus(artifact.status)}
          />
        </div>

        <div className="mt-5">
          <h3 className="text-sm font-semibold text-[var(--sh-ink-strong)]">内容草稿</h3>
          {draftEditor ?? (
            <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 text-sm leading-6 text-[var(--sh-ink-muted)]">
              {draftUnavailableMessage}
            </p>
          )}
        </div>

        {conflictMessage ? (
          <p
            className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
            role="alert"
          >
            {conflictMessage}
          </p>
        ) : null}
        {onSaveDraft || onSubmit ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {onSaveDraft ? (
              <Button
                disabled={writeDisabled || writePending || !draftContentReady}
                onClick={onSaveDraft}
              >
                保存草稿
              </Button>
            ) : null}
            {onSubmit ? (
              <Button
                disabled={
                  writeDisabled || writePending || !artifact.current_draft || !draftContentReady
                }
                onClick={() => onSubmit(draftBranch)}
                variant="secondary"
              >
                提交当前草稿
              </Button>
            ) : null}
          </div>
        ) : null}
      </section>

      <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <h2 className="font-semibold text-[var(--sh-ink-strong)]">版本审核</h2>
        {submitted && !submittedIsApproved ? (
          <div className="mt-4">
            <p className="text-sm text-[var(--sh-ink-muted)]">
              当前待确认版本：{submitted.version_no}
            </p>
            {submittedVersionPreview ?? (
              <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm leading-6 text-[var(--sh-warning)]">
                {reviewUnavailableMessage}
              </p>
            )}
            {onApprove ? (
              <Button
                className="mt-4 w-full"
                disabled={writeDisabled || writePending || !reviewContentReady}
                onClick={() => onApprove(submitted.id)}
              >
                批准当前版本
              </Button>
            ) : null}
          </div>
        ) : (
          <p className="mt-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
            {submittedIsApproved
              ? "当前提交版本已经批准，无需重复确认。"
              : "尚无待确认版本。完成草稿后再提交审核。"}
          </p>
        )}
        {approved ? (
          <p className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-3 text-sm text-[var(--sh-success)]">
            已批准版本 {approved.version_no}
          </p>
        ) : null}
      </aside>
    </div>
  );
}
