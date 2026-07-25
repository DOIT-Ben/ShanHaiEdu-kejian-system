import { BookOpenCheck } from "lucide-react";
import { useEffect, useState } from "react";
import type { ArtifactDto } from "@/features/artifacts/api/artifactsApi";
import type { GenerationJobDto } from "@/features/jobs/api/jobsApi";
import type { MaterialParseVersionDto } from "@/features/materials/api/materialsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { Button } from "@/shared/ui/Button";

type MaterialScopeWorkflowPanelProps = {
  actionError?: string;
  artifact?: ArtifactDto;
  busyAction?: "approve" | "generate" | "scope";
  job?: GenerationJobDto;
  jobError?: string;
  jobLoading?: boolean;
  onApprove: () => void;
  onGenerate: () => void;
  onRefreshJob: () => void;
  onSubmitScope: (pageStart: number, pageEnd: number) => void;
  parseVersion?: MaterialParseVersionDto;
  writeReady: boolean;
};

function scopeRange(artifact: ArtifactDto | undefined) {
  const version = artifact?.current_submitted_version ?? artifact?.current_approved_version;
  const content: Record<string, unknown> | undefined = version?.content;
  const pageStart = content?.page_start;
  const pageEnd = content?.page_end;
  return typeof pageStart === "number" && typeof pageEnd === "number"
    ? { pageEnd, pageStart }
    : undefined;
}

export function MaterialScopeWorkflowPanel({
  actionError,
  artifact,
  busyAction,
  job,
  jobError,
  jobLoading,
  onApprove,
  onGenerate,
  onRefreshJob,
  onSubmitScope,
  parseVersion,
  writeReady,
}: MaterialScopeWorkflowPanelProps) {
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const pageCount = parseVersion?.page_count ?? 0;
  const currentRange = scopeRange(artifact);
  const pendingVersion = artifact?.current_submitted_version;
  const approvedVersion =
    artifact?.status === "approved" ? artifact.current_approved_version : null;
  const rangeValid =
    pageCount > 0 && pageStart >= 1 && pageStart <= pageEnd && pageEnd <= pageCount;

  useEffect(() => {
    if (!parseVersion?.page_count) return;
    setPageStart(1);
    setPageEnd(parseVersion.page_count);
  }, [parseVersion?.id, parseVersion?.page_count]);

  return (
    <div className="space-y-5">
      <section
        className="border-t border-[var(--sh-line-subtle)] pt-5"
        aria-labelledby="scope-title"
      >
        <div className="flex items-start gap-3">
          <BookOpenCheck
            aria-hidden="true"
            className="mt-0.5 size-5 shrink-0 text-[var(--sh-brand-600)]"
          />
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="scope-title">
              确认教材物理页范围
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--sh-ink-muted)]">
              只使用已成功解析的实际 PDF 页码，后续课时划分会固定绑定这个版本。
            </p>
          </div>
        </div>

        {parseVersion ? (
          <div className="mt-4 grid gap-4 sm:grid-cols-[minmax(0,180px)_minmax(0,180px)_auto] sm:items-end">
            <label className="text-sm font-medium text-[var(--sh-ink-default)]">
              起始物理页
              <input
                className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3"
                max={pageCount}
                min={1}
                onChange={(event) => setPageStart(event.target.valueAsNumber)}
                type="number"
                value={Number.isNaN(pageStart) ? "" : pageStart}
              />
            </label>
            <label className="text-sm font-medium text-[var(--sh-ink-default)]">
              结束物理页
              <input
                className="mt-2 min-h-10 w-full rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3"
                max={pageCount}
                min={1}
                onChange={(event) => setPageEnd(event.target.valueAsNumber)}
                type="number"
                value={Number.isNaN(pageEnd) ? "" : pageEnd}
              />
            </label>
            <Button
              disabled={
                !writeReady ||
                !rangeValid ||
                busyAction !== undefined ||
                (pendingVersion !== null && pendingVersion !== undefined)
              }
              onClick={() => onSubmitScope(pageStart, pageEnd)}
            >
              {approvedVersion ? "提交新教材范围" : "提交教材范围"}
            </Button>
          </div>
        ) : (
          <p className="mt-4 text-sm text-[var(--sh-ink-muted)]">
            教材成功解析后即可选择物理页范围。
          </p>
        )}

        {currentRange && pendingVersion ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-4">
            <p className="text-sm text-[var(--sh-warning)]">
              教材范围待批准：第 {currentRange.pageStart}-{currentRange.pageEnd} 页
            </p>
            <Button
              disabled={!writeReady || busyAction !== undefined}
              onClick={onApprove}
              variant="secondary"
            >
              批准教材范围
            </Button>
          </div>
        ) : currentRange && approvedVersion ? (
          <p className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] p-4 text-sm text-[var(--sh-success)]">
            已批准教材范围：第 {currentRange.pageStart}-{currentRange.pageEnd} 页
          </p>
        ) : null}

        {!writeReady ? (
          <p className="mt-3 text-sm text-[var(--sh-warning)]" role="status">
            当前会话仅支持查看教材，无法提交或批准范围。
          </p>
        ) : null}
        {actionError ? (
          <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
            {actionError}
          </p>
        ) : null}
      </section>

      <section
        className="border-t border-[var(--sh-line-subtle)] pt-5"
        aria-labelledby="division-title"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold text-[var(--sh-ink-strong)]" id="division-title">
              课时划分
            </h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              生成任务在后台 Worker 中执行，离开页面后仍可恢复进度。
            </p>
          </div>
          {approvedVersion && !job ? (
            <Button disabled={!writeReady || busyAction !== undefined} onClick={onGenerate}>
              生成课时划分
            </Button>
          ) : null}
        </div>

        {job || jobLoading || jobError ? (
          <div className="mt-4">
            <GenerationJobPanel
              errorMessage={jobError}
              job={job}
              loading={jobLoading}
              onRefresh={onRefreshJob}
            />
          </div>
        ) : !approvedVersion ? (
          <p className="mt-4 text-sm text-[var(--sh-ink-muted)]">
            先批准教材范围，再生成课时划分。
          </p>
        ) : null}
      </section>
    </div>
  );
}
