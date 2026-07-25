import { BookOpenCheck, CheckCircle2, FileText } from "lucide-react";
import { useEffect, useState } from "react";
import type {
  MaterialParsePageDto,
  MaterialParseVersionDto,
} from "@/features/materials/api/materialsApi";
import {
  useApproveMaterialScopeMutation,
  useCreateMaterialScopeMutation,
  type useMaterialScopeRuntime,
} from "@/features/materials/hooks/useMaterialScopeWorkflow";
import { materialScopeVersionMatches } from "@/features/materials/lib/materialScopeIdentity";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type MaterialScopeRuntime = ReturnType<typeof useMaterialScopeRuntime>;

function contentRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

export function MaterialScopePanel({
  materialId,
  pages,
  parseVersion,
  projectId,
  runtime,
}: {
  materialId: string;
  pages: readonly MaterialParsePageDto[];
  parseVersion?: MaterialParseVersionDto;
  projectId: string;
  runtime: MaterialScopeRuntime;
}) {
  const [pageStart, setPageStart] = useState(1);
  const [pageEnd, setPageEnd] = useState(1);
  const { artifact, latestApproval, refetch } = runtime;
  const createMutation = useCreateMaterialScopeMutation({ projectId, refetch });
  const candidateVersion =
    artifact?.current_submitted_version ?? artifact?.current_approved_version;
  const exactScope = materialScopeVersionMatches(candidateVersion, materialId, parseVersion?.id);
  const submittedVersionId = exactScope ? artifact?.current_submitted_version?.id : undefined;
  const approveMutation = useApproveMaterialScopeMutation({
    projectId,
    refetch,
    versionId: submittedVersionId,
  });
  const approved =
    artifact?.status === "approved" &&
    artifact.current_approved_version?.id === latestApproval?.artifact_version_id &&
    latestApproval?.action === "approve" &&
    exactScope;
  const currentContent = exactScope ? contentRecord(candidateVersion?.content) : undefined;

  useEffect(() => {
    const count = parseVersion?.page_count ?? pages.length;
    setPageStart(1);
    setPageEnd(Math.max(1, count));
  }, [pages.length, parseVersion?.id, parseVersion?.page_count]);

  const writeReady = isCsrfTokenAvailable();
  const rangeValid =
    parseVersion?.status === "succeeded" &&
    pages.length > 0 &&
    pageStart >= 1 &&
    pageStart <= pageEnd &&
    pageEnd <= pages.length;
  const actionError = createMutation.error ?? approveMutation.error;

  return (
    <section className="border-t border-[var(--sh-line-subtle)] pt-6" aria-labelledby="scope-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <BookOpenCheck aria-hidden="true" className="size-5 text-[var(--sh-brand-600)]" />
            <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]" id="scope-title">
              教材范围
            </h2>
          </div>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">按真实解析页选择本次教学内容。</p>
        </div>
        {exactScope ? (
          <StatusBadge status={approved ? "approved" : "review_required"} />
        ) : (
          <StatusBadge status={rangeValid ? "ready" : "not_ready"} />
        )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {pages.map((page) => {
          const selected = page.page_number >= pageStart && page.page_number <= pageEnd;
          return (
            <article
              className={`min-h-36 rounded-[var(--sh-radius-md)] border p-4 ${
                selected
                  ? "border-[var(--sh-brand-300)] bg-[var(--sh-brand-50)]"
                  : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"
              }`}
              key={page.page_number}
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="font-semibold text-[var(--sh-ink-strong)]">
                  物理页 {page.page_number}
                </h3>
                {selected ? (
                  <CheckCircle2 aria-hidden="true" className="size-4 text-[var(--sh-brand-600)]" />
                ) : null}
              </div>
              <p className="mt-2 line-clamp-3 text-sm leading-6 text-[var(--sh-ink-muted)]">
                {page.text_preview || "本页未提取到文字，可依据图片数量核对。"}
              </p>
              <p className="mt-3 flex items-center gap-1.5 text-xs text-[var(--sh-ink-faint)]">
                <FileText aria-hidden="true" className="size-3.5" />
                {page.text_block_count} 个文字块 · {page.image_count} 张图片
              </p>
            </article>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium text-[var(--sh-ink-default)]">
          起始物理页
          <input
            className="mt-1 block h-10 w-28 rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3"
            max={pages.length || 1}
            min={1}
            onChange={(event) => setPageStart(event.currentTarget.valueAsNumber || 1)}
            type="number"
            value={pageStart}
          />
        </label>
        <label className="text-sm font-medium text-[var(--sh-ink-default)]">
          结束物理页
          <input
            className="mt-1 block h-10 w-28 rounded-[var(--sh-radius-control)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-elevated)] px-3"
            max={pages.length || 1}
            min={1}
            onChange={(event) => setPageEnd(event.currentTarget.valueAsNumber || 1)}
            type="number"
            value={pageEnd}
          />
        </label>
        <Button
          disabled={
            !writeReady || !rangeValid || createMutation.isPending || approveMutation.isPending
          }
          loading={createMutation.isPending}
          loadingText="正在保存范围"
          onClick={() =>
            parseVersion &&
            createMutation.mutate({
              material_parse_version_id: parseVersion.id,
              page_end: pageEnd,
              page_start: pageStart,
              source_material_id: materialId,
            })
          }
          variant="secondary"
        >
          {exactScope ? "保存新的范围版本" : "保存教材范围"}
        </Button>
        {exactScope && artifact?.status === "in_review" && submittedVersionId ? (
          <Button
            disabled={!writeReady || approveMutation.isPending}
            loading={approveMutation.isPending}
            loadingText="正在确认范围"
            onClick={() => approveMutation.mutate()}
          >
            确认当前范围
          </Button>
        ) : null}
      </div>

      {currentContent ? (
        <p className="mt-3 text-sm text-[var(--sh-ink-muted)]" role="status">
          已保存范围：物理页 {String(currentContent.page_start)} 至{" "}
          {String(currentContent.page_end)}
          {approved ? "，教师已确认。" : "，等待教师确认。"}
        </p>
      ) : null}
      {actionError ? (
        <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(actionError, "教材范围没有保存，请核对页码后重试。")}
        </p>
      ) : null}
    </section>
  );
}
