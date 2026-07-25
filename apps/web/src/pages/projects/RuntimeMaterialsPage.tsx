import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  useArtifactApprovalMutation,
  useArtifactQualityMutation,
} from "@/features/artifacts/hooks/useArtifactReviewMutations";
import { MaterialDetailsPanel } from "@/features/materials/components/MaterialDetailsPanel";
import { MaterialScopeWorkflowPanel } from "@/features/materials/components/MaterialScopeWorkflowPanel";
import {
  useCreateMaterialScopeMutation,
  useLessonDivisionGenerationMutation,
  useLessonDivisionJobRuntime,
  useProjectArtifactsRuntime,
  useProjectMaterialsRuntime,
} from "@/features/materials/hooks/useRuntimeMaterialsWorkflow";
import { LessonDivisionReviewPanel } from "@/features/lessons/components/LessonDivisionReviewPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

export function RuntimeMaterialsPage() {
  const { materialId, projectId } = useParams();
  const [qualityRequestedVersionId, setQualityRequestedVersionId] = useState<string>();
  useProjectEvents(projectId);

  const { latestSucceededParse, materialQuery, materialsQuery, selectedMaterialId } =
    useProjectMaterialsRuntime(projectId, materialId);
  const { artifactsKey, artifactsQuery, lessonDivision, materialScope } =
    useProjectArtifactsRuntime(projectId);
  const { job, jobQuery, jobsKey, jobsQuery, setStartedJobId, workflowQuery } =
    useLessonDivisionJobRuntime(projectId);
  const scopeMutation = useCreateMaterialScopeMutation({
    artifactsKey,
    parseVersion: latestSucceededParse,
    projectId,
    selectedMaterialId,
  });
  const approvalMutation = useArtifactApprovalMutation({
    artifactVersionId: materialScope?.current_submitted_version?.id,
    comment: "教材物理页范围已确认",
    missingVersionError: "MATERIAL_SCOPE_VERSION_MISSING",
    refetchArtifact: artifactsQuery.refetch,
  });
  const generationMutation = useLessonDivisionGenerationMutation({
    jobsKey,
    materialScope,
    onStarted: setStartedJobId,
    projectId,
  });
  const divisionQualityMutation = useArtifactQualityMutation({
    artifactVersionId: lessonDivision?.current_submitted_version?.id,
    missingVersionError: "LESSON_DIVISION_VERSION_MISSING",
    onRequested: setQualityRequestedVersionId,
  });
  const divisionApprovalMutation = useArtifactApprovalMutation({
    artifactVersionId: lessonDivision?.current_submitted_version?.id,
    comment: "课时划分已审阅确认",
    missingVersionError: "LESSON_DIVISION_VERSION_MISSING",
    refetchArtifact: artifactsQuery.refetch,
  });

  if (!projectId) return null;

  const mutationError = scopeMutation.error ?? approvalMutation.error ?? generationMutation.error;
  const busyAction = scopeMutation.isPending
    ? "scope"
    : approvalMutation.isPending
      ? "approve"
      : generationMutation.isPending
        ? "generate"
        : undefined;
  const divisionError = divisionQualityMutation.error ?? divisionApprovalMutation.error;
  const divisionBusyAction = divisionQualityMutation.isPending
    ? "quality"
    : divisionApprovalMutation.isPending
      ? "approve"
      : undefined;

  return (
    <div className="mx-auto max-w-[980px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link
            className={buttonVariants({ variant: "secondary" })}
            to={`/app/projects/${projectId}`}
          >
            <ArrowLeft aria-hidden="true" />
            返回项目
          </Link>
        }
        description="确认教材物理页范围，并从正式任务恢复课时划分进度。"
        title="教材范围与课时划分"
      />

      <div className="mt-5 space-y-5">
        {materialsQuery.data?.items.length ? (
          <nav aria-label="项目教材" className="flex flex-wrap gap-2">
            {materialsQuery.data.items.map((material) => (
              <Link
                aria-current={material.id === selectedMaterialId ? "page" : undefined}
                className={buttonVariants({
                  variant: material.id === selectedMaterialId ? "primary" : "secondary",
                })}
                key={material.id}
                to={`/app/projects/${projectId}/materials/${material.id}`}
              >
                {material.original_filename}
              </Link>
            ))}
          </nav>
        ) : null}

        {selectedMaterialId ? (
          <>
            <MaterialDetailsPanel
              asset={materialQuery.data?.asset}
              errorMessage={
                materialQuery.isError
                  ? runtimeErrorMessage(materialQuery.error, "教材状态暂时无法读取，请稍后重试。")
                  : materialQuery.data?.partialError
              }
              loading={materialQuery.isFetching}
              onRefresh={() => void materialQuery.refetch()}
              parseVersions={materialQuery.data?.parseVersions ?? []}
            />
            <MaterialScopeWorkflowPanel
              actionError={
                mutationError
                  ? runtimeErrorMessage(mutationError, "当前操作没有完成，请刷新正式状态后重试。")
                  : artifactsQuery.isError
                    ? runtimeErrorMessage(
                        artifactsQuery.error,
                        "教材范围暂时无法恢复，请稍后重试。",
                      )
                    : undefined
              }
              artifact={materialScope}
              busyAction={busyAction}
              job={job?.project_id === projectId ? job : undefined}
              jobError={
                jobQuery.isError
                  ? runtimeErrorMessage(jobQuery.error, "课时划分任务暂时无法读取。")
                  : jobsQuery.isError
                    ? runtimeErrorMessage(jobsQuery.error, "课时划分任务列表暂时无法读取。")
                    : undefined
              }
              jobLoading={jobQuery.isFetching || jobsQuery.isLoading}
              onApprove={() => approvalMutation.mutate()}
              onGenerate={() => generationMutation.mutate()}
              onRefreshJob={() => void jobQuery.refetch()}
              onSubmitScope={(pageStart, pageEnd) => scopeMutation.mutate({ pageEnd, pageStart })}
              parseVersion={latestSucceededParse}
              writeReady={isCsrfTokenAvailable()}
            />
            {lessonDivision ? (
              <LessonDivisionReviewPanel
                artifact={lessonDivision}
                busyAction={divisionBusyAction}
                errorMessage={
                  divisionError
                    ? runtimeErrorMessage(
                        divisionError,
                        "课时划分尚未批准；请等待质量校验完成后重试。",
                      )
                    : undefined
                }
                onApprove={() => divisionApprovalMutation.mutate()}
                onQuality={() => divisionQualityMutation.mutate()}
                projectId={projectId}
                qualityAccepted={
                  qualityRequestedVersionId === lessonDivision.current_submitted_version?.id
                    ? divisionQualityMutation.data
                    : undefined
                }
                qualityNodeRuns={workflowQuery.data?.node_runs}
                writeReady={isCsrfTokenAvailable()}
              />
            ) : null}
          </>
        ) : materialsQuery.isLoading ? (
          <div
            className="h-48 animate-pulse rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
            role="status"
          >
            <span className="sr-only">正在读取项目教材</span>
          </div>
        ) : (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">教材详情暂时无法打开</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              {materialsQuery.isError
                ? "项目教材暂时无法读取，请检查网络后重试。"
                : "当前项目还没有已上传的教材。请返回项目重新上传教材。"}
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
