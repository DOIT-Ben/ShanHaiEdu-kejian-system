import type { NodeRun, ValidationIssue } from "@/shared/api";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { parseContentDefinition, type ContentDefinition } from "@/entities/content";
import { ContentDefinitionRenderer } from "@/features/content-definition";
import { useArtifactVersion, useNodeRunDetail, useSaveArtifactContent } from "@/features/node-runs";
import { ApprovalActions } from "@/features/approvals";
import { AppError } from "@/shared/api";
import { useDebouncedCallback } from "@/shared/hooks";
import { SaveStatusIndicator, Skeleton, toast, type SaveState } from "@/shared/ui";
import { useStepNodeRun, useWorkbench } from "../context";
import { StepScaffold, StaleBanner } from "../parts";

/**
 * 修改并确认教案：白纸画布直接编辑（05 §2 直接可编辑），
 * 自动保存（防抖 + If-Match），批准前警告逐条确认。
 */
export function LessonPlanConfirmCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: detail } = useNodeRunDetail(nodeRun?.id ?? null);
  const versionId = detail?.node_run.current_artifact_version_id ?? null;
  const { data: artifactData } = useArtifactVersion(versionId);

  if (isPending || !nodeRun) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  const status = detail?.node_run.status ?? nodeRun.status;

  if (!versionId || !artifactData) {
    return (
      <StepScaffold title="修改并确认教案" status={status}>
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          还没有可确认的教案。
          <Link
            to={`/app/projects/${projectId}/lessons/${lessonId}/work/lesson-plan`}
            className="ml-1 font-medium text-brand-600 hover:underline"
          >
            先生成教案
          </Link>
        </p>
      </StepScaffold>
    );
  }

  return (
    <PlanEditor
      key={versionId}
      versionId={versionId}
      etag={artifactData.etag ?? ""}
      nodeRun={detail?.node_run ?? nodeRun}
      content={artifactData.version.content as { definition?: unknown; data?: Record<string, unknown> }}
      validationIssues={artifactData.version.validation_issues ?? []}
      reviewStatus={artifactData.version.review_status}
      versionNo={artifactData.version.version_no}
    />
  );
}

function PlanEditor({
  versionId,
  etag,
  nodeRun,
  content,
  validationIssues,
  reviewStatus,
  versionNo,
}: {
  versionId: string;
  etag: string;
  nodeRun: NodeRun;
  content: { definition?: unknown; data?: Record<string, unknown> };
  validationIssues: ValidationIssue[];
  reviewStatus: string;
  versionNo: number;
}) {
  const status = nodeRun.status;
  const nodeRunId = nodeRun.id;
  const definition = useMemo<ContentDefinition | null>(() => {
    if (!content.definition) return null;
    try {
      return parseContentDefinition(content.definition);
    } catch {
      return null;
    }
  }, [content.definition]);

  const [data, setData] = useState<Record<string, unknown>>(content.data ?? {});
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const save = useSaveArtifactContent(versionId);
  const etagRef = useRef(etag);
  useEffect(() => {
    etagRef.current = etag;
  }, [etag]);

  const readOnly = reviewStatus === "approved" || reviewStatus === "superseded";

  const persist = useDebouncedCallback((next: Record<string, unknown>) => {
    setSaveState("saving");
    save.mutate(
      { etag: etagRef.current, content: { definition: content.definition, data: next } },
      {
        onSuccess: (result) => {
          etagRef.current = result.etag ?? etagRef.current;
          setSaveState("saved");
        },
        onError: (error) => {
          if (error instanceof AppError && error.isEditConflict) {
            setSaveState("error");
            toast({
              tone: "warning",
              title: "内容已在其他位置修改",
              description: "请刷新页面查看最新版本后继续编辑。",
            });
          } else {
            setSaveState("error");
            toast({ tone: "danger", title: "保存失败", description: error.message });
          }
        },
      },
    );
  }, 800);

  const handleChange = (next: Record<string, unknown>) => {
    setData(next);
    setSaveState("saving");
    persist.run(next);
  };

  if (!definition) {
    return (
      <StepScaffold title="修改并确认教案" status={status}>
        <p className="rounded-lg border border-warning-200 bg-warning-50 p-6 text-sm text-ink" role="alert">
          教案内容缺少可识别的内容定义，无法编辑。请联系管理员检查内容规范版本。
        </p>
      </StepScaffold>
    );
  }

  return (
    <StepScaffold
      title="修改并确认教案"
      description={
        readOnly
          ? `第 ${versionNo} 版 · 已批准（批准后内容只读；如需调整请重新生成）`
          : `第 ${versionNo} 版 · 直接点击内容即可修改，修改自动保存`
      }
      status={status}
      secondaryActions={!readOnly ? <SaveStatusIndicator state={saveState} /> : undefined}
      primaryAction={
        !readOnly ? (
          <ApprovalActions
            versionId={versionId}
            nodeRunId={nodeRunId}
            validationIssues={validationIssues}
            approveLabel="确认教案"
          />
        ) : undefined
      }
    >
      {status === "stale" ? <StaleBanner nodeRun={nodeRun} /> : null}
      <article className="sh-paper-canvas mx-auto max-w-3xl rounded-lg border border-line-subtle p-8 shadow-card sm:p-10">
        <h1 className="text-center text-xl font-semibold text-ink-strong">{definition.title}</h1>
        <div className="mt-8">
          <ContentDefinitionRenderer
            definition={definition}
            value={data}
            onChange={readOnly ? undefined : handleChange}
            readOnly={readOnly}
            issues={validationIssues}
          />
        </div>
      </article>
    </StepScaffold>
  );
}
