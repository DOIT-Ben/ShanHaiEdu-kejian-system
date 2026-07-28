import type { ReactElement, ReactNode } from "react";
import type { ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import type { WorkflowStatus } from "@/entities/workflow/model";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type ArtifactWorkbenchProps = {
  artifact: ArtifactDto;
  busyAction?: "approve" | "save" | "submit";
  completedAction?: "approve" | "save" | "submit";
  conflictMessage?: string;
  contentNavigation?: ReactNode;
  draftEditor?: ReactElement;
  draftUnavailableMessage?: string;
  onApprove?: (versionId: string) => void;
  onSaveDraft?: () => void;
  onSubmit?: (draftBranch: string) => void;
  reviewStatus?: ReactNode;
  reviewUnavailableMessage?: string;
  submittedVersionPreview?: ReactElement;
  title: string;
  variant?: "default" | "document";
  writeDisabled?: boolean;
  writeDisabledMessage?: string;
};

function artifactStatus(status: ArtifactDto["status"]): WorkflowStatus {
  if (status === "in_review") return "review_required";
  if (status === "archived") return "disabled";
  return status;
}

export function ArtifactWorkbench({
  artifact,
  busyAction,
  completedAction,
  conflictMessage,
  contentNavigation,
  draftEditor,
  draftUnavailableMessage = "草稿正文暂不可查看或编辑，保存和提交已停用。",
  onApprove,
  onSaveDraft,
  onSubmit,
  reviewStatus,
  reviewUnavailableMessage = "待确认版本正文暂不可查看，批准操作已停用。",
  submittedVersionPreview,
  title,
  variant = "default",
  writeDisabled = false,
  writeDisabledMessage,
}: ArtifactWorkbenchProps) {
  const draftBranch = artifact.current_draft?.draft_branch ?? "main";
  const submitted = artifact.current_submitted_version;
  const approved = artifact.current_approved_version;
  const writePending = busyAction !== undefined;
  const submittedIsApproved = Boolean(submitted && approved && submitted.id === approved.id);
  const draftContentReady = draftEditor !== undefined;
  const reviewContentReady = submittedVersionPreview !== undefined;

  const draftActions =
    onSaveDraft || onSubmit ? (
      <div aria-label="教案操作" className="flex flex-wrap gap-2" role="group">
        {onSaveDraft ? (
          <Button
            className="min-h-11"
            disabled={
              writeDisabled || writePending || completedAction === "save" || !draftContentReady
            }
            loading={busyAction === "save"}
            loadingText="正在保存"
            onClick={onSaveDraft}
            success={completedAction === "save"}
            successText="保存成功"
          >
            保存草稿
          </Button>
        ) : null}
        {onSubmit ? (
          <Button
            className="min-h-11"
            disabled={
              writeDisabled ||
              writePending ||
              completedAction === "submit" ||
              !artifact.current_draft ||
              !draftContentReady
            }
            loading={busyAction === "submit"}
            loadingText="正在提交"
            onClick={() => onSubmit(draftBranch)}
            success={completedAction === "submit"}
            successText="提交成功"
            variant="secondary"
          >
            提交当前草稿
          </Button>
        ) : null}
      </div>
    ) : null;

  const reviewPanel = (
    <>
      {reviewStatus}
      {submitted && !submittedIsApproved ? (
        <div className="mt-5 border-t border-[var(--sh-line-subtle)] pt-5">
          <p className="text-sm font-medium text-[var(--sh-ink-strong)]">
            待批准版本 {submitted.version_no}
          </p>
          <p className="mt-1 text-xs leading-5 text-[var(--sh-ink-muted)]">
            质量检查通过后，批准将精确绑定此版本。
          </p>
          {!reviewContentReady ? (
            <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm leading-6 text-[var(--sh-warning-strong)]">
              {reviewUnavailableMessage}
            </p>
          ) : null}
          {onApprove ? (
            <Button
              className="mt-4 min-h-11 w-full"
              disabled={
                writeDisabled ||
                writePending ||
                completedAction === "approve" ||
                !reviewContentReady
              }
              loading={busyAction === "approve"}
              loadingText="正在批准"
              onClick={() => onApprove(submitted.id)}
              success={completedAction === "approve"}
              successText="批准成功"
            >
              批准当前版本
            </Button>
          ) : null}
        </div>
      ) : (
        <p className="mt-4 text-sm leading-6 text-[var(--sh-ink-muted)]">
          {submittedIsApproved
            ? "当前提交版本已经批准，无需重复确认。"
            : "尚无待批准版本。保存草稿后提交质量检查。"}
        </p>
      )}
      {approved ? (
        <p className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-3 text-sm font-medium text-[var(--sh-success-strong)]">
          已批准版本 {approved.version_no}
        </p>
      ) : null}
    </>
  );

  if (variant === "document") {
    return (
      <div className="grid items-start border-y border-[var(--sh-line-default)] bg-[var(--sh-line-subtle)] xl:grid-cols-[190px_minmax(0,1fr)_280px]">
        <aside className="order-2 min-w-0 bg-[var(--sh-surface-base)] p-4 xl:order-1 xl:sticky xl:top-[calc(var(--sh-topbar-height)+1rem)] xl:max-h-[calc(100dvh-var(--sh-topbar-height)-2rem)] xl:overflow-y-auto">
          {contentNavigation}
        </aside>

        <section
          aria-labelledby="artifact-document-title"
          className="order-1 min-w-0 border-y border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)] px-4 py-5 md:px-7 xl:order-2 xl:border-x xl:border-y-0"
        >
          <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-[var(--sh-ink-faint)]">当前草稿</p>
              <h2
                className="mt-1 text-lg font-semibold text-[var(--sh-ink-strong)]"
                id="artifact-document-title"
              >
                {title}
              </h2>
            </div>
          </div>

          {draftActions ? (
            <div className="sticky top-[var(--sh-topbar-height)] z-20 -mx-4 mt-4 border-y border-[var(--sh-line-subtle)] bg-[var(--sh-surface-paper)]/95 px-4 py-3 backdrop-blur-[10px] md:-mx-7 md:px-7">
              {draftActions}
              {writeDisabled && writeDisabledMessage ? (
                <p className="mt-2 text-sm leading-6 text-[var(--sh-warning-strong)]" role="status">
                  {writeDisabledMessage}
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="mt-5">
            {draftEditor ?? (
              <p className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-4 text-sm leading-6 text-[var(--sh-ink-muted)]">
                {draftUnavailableMessage}
              </p>
            )}
          </div>

          {conflictMessage ? (
            <p
              className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning-strong)]"
              role="alert"
            >
              {conflictMessage}
            </p>
          ) : null}

          {submitted && submittedVersionPreview ? (
            <details className="mt-6 border-y border-[var(--sh-line-default)] py-4">
              <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-[var(--sh-ink-strong)] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)]">
                查看待批准版本 {submitted.version_no}
              </summary>
              <div className="mt-4">{submittedVersionPreview}</div>
            </details>
          ) : null}
        </section>

        <aside className="order-3 min-w-0 bg-[var(--sh-surface-elevated)] p-5 xl:sticky xl:top-[calc(var(--sh-topbar-height)+1rem)] xl:max-h-[calc(100dvh-var(--sh-topbar-height)-2rem)] xl:overflow-y-auto">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">状态与审批</h2>
            <StatusBadge
              label={artifact.status === "archived" ? "已归档" : undefined}
              status={artifactStatus(artifact.status)}
            />
          </div>
          {reviewPanel}
        </aside>
      </div>
    );
  }

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
            className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning-strong)]"
            role="alert"
          >
            {conflictMessage}
          </p>
        ) : null}
        {draftActions ? (
          <div className="mt-4">
            {draftActions}
            {writeDisabled && writeDisabledMessage ? (
              <p className="mt-2 text-sm leading-6 text-[var(--sh-warning-strong)]" role="status">
                {writeDisabledMessage}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
        <h2 className="font-semibold text-[var(--sh-ink-strong)]">版本审核</h2>
        {submitted && !submittedIsApproved && submittedVersionPreview ? (
          <div className="mt-4">{submittedVersionPreview}</div>
        ) : null}
        {reviewPanel}
      </aside>
    </div>
  );
}
