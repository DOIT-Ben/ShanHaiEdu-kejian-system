import { RefreshCw } from "lucide-react";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import {
  useLessonDivisionGenerationMutation,
  useLessonDivisionJobRuntime,
} from "@/features/lessons/hooks/useLessonDivisionWorkflow";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { Button } from "@/shared/ui/Button";

export function LessonDivisionGenerationPanel({
  artifactStatus,
  materialScopeVersionId,
  projectId,
}: {
  artifactStatus?: string;
  materialScopeVersionId?: string;
  projectId: string;
}) {
  const jobRuntime = useLessonDivisionJobRuntime(projectId);
  const generationMutation = useLessonDivisionGenerationMutation({
    onStarted: jobRuntime.setStartedJobId,
    projectId,
  });
  const jobLive = Boolean(
    jobRuntime.job && !["succeeded", "failed", "cancelled"].includes(jobRuntime.job.status),
  );
  const artifactBlocksGeneration = Boolean(artifactStatus && artifactStatus !== "stale");

  return (
    <>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          disabled={
            !isCsrfTokenAvailable() ||
            !materialScopeVersionId ||
            generationMutation.isPending ||
            jobLive ||
            artifactBlocksGeneration
          }
          loading={generationMutation.isPending}
          loadingText="正在启动课时划分"
          onClick={() =>
            materialScopeVersionId && generationMutation.mutate(materialScopeVersionId)
          }
        >
          <RefreshCw aria-hidden="true" />
          {artifactStatus === "stale"
            ? "重新生成课时划分"
            : artifactStatus
              ? "课时划分已生成"
              : "生成课时划分"}
        </Button>
        {!materialScopeVersionId ? (
          <p className="text-sm text-[var(--sh-ink-muted)]" role="status">
            先确认教材范围，再启动课时划分。
          </p>
        ) : null}
      </div>

      {generationMutation.error ? (
        <p className="mt-3 text-sm text-[var(--sh-danger)]" role="alert">
          {runtimeErrorMessage(generationMutation.error, "课时划分没有启动，请刷新后重试。")}
        </p>
      ) : null}

      {jobRuntime.job || jobRuntime.jobsQuery.isLoading || jobRuntime.jobsQuery.error ? (
        <div className="mt-4">
          <GenerationJobPanel
            errorMessage={
              jobRuntime.jobsQuery.error || jobRuntime.jobQuery.error
                ? runtimeErrorMessage(
                    jobRuntime.jobsQuery.error ?? jobRuntime.jobQuery.error,
                    "课时划分任务状态暂时无法读取。",
                  )
                : undefined
            }
            job={jobRuntime.job}
            loading={jobRuntime.jobsQuery.isLoading || jobRuntime.jobQuery.isFetching}
            onRefresh={() => void jobRuntime.jobQuery.refetch()}
            title="课时划分进度"
          />
        </div>
      ) : null}
    </>
  );
}
