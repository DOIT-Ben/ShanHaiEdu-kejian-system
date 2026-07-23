import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import {
  cancelGenerationJob,
  getGenerationJob,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useJobEvents } from "@/shared/api/useJobEvents";
import { buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const terminalStatuses = new Set<GenerationJobDto["status"]>(["succeeded", "failed", "cancelled"]);

export function RuntimeJobPage() {
  const { jobId, projectId } = useParams();
  const queryClient = useQueryClient();
  const cancelIntentRef = useRef<string | undefined>(undefined);

  const jobKey = ["generation-jobs", jobId] as const;
  const jobQuery = useQuery({
    enabled: Boolean(jobId),
    queryFn: () => getGenerationJob(jobId ?? ""),
    queryKey: jobKey,
    refetchInterval: (query) => {
      const job = query.state.data;
      if (job && job.project_id !== projectId) return false;
      const status = job?.status;
      return status && terminalStatuses.has(status) ? false : 5_000;
    },
  });
  const job = jobQuery.data;
  const jobStatus = job?.status;
  useEffect(() => {
    if (jobStatus && terminalStatuses.has(jobStatus)) cancelIntentRef.current = undefined;
  }, [jobStatus]);
  const jobOwnedByProject = Boolean(projectId && job?.project_id === projectId);
  const jobNeedsLiveUpdates = Boolean(
    jobOwnedByProject && job && !terminalStatuses.has(job.status),
  );
  useJobEvents(
    jobNeedsLiveUpdates ? jobId : undefined,
    jobNeedsLiveUpdates ? projectId : undefined,
  );

  const cancelMutation = useMutation({
    mutationFn: () => {
      if (!jobId || job?.project_id !== projectId) {
        throw new Error("GENERATION_JOB_CANCEL_NOT_ALLOWED");
      }
      const idempotencyKey = cancelIntentRef.current ?? crypto.randomUUID();
      cancelIntentRef.current = idempotencyKey;
      return cancelGenerationJob({ idempotencyKey, jobId });
    },
    onSuccess: async (cancelledJob) => {
      cancelIntentRef.current = undefined;
      queryClient.setQueryData(jobKey, cancelledJob);
      await queryClient.invalidateQueries({ exact: true, queryKey: jobKey });
    },
  });

  if (!projectId || !jobId) return null;

  const writeReady = isCsrfTokenAvailable();
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
        description="页面会自动恢复并显示任务的最新进度。"
        title="任务进度"
      />

      <div className="mt-5">
        {job && !jobOwnedByProject ? (
          <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6">
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">任务暂时无法打开</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
              请返回当前项目，从任务列表重新进入。
            </p>
          </section>
        ) : (
          <GenerationJobPanel
            cancelLabel={cancelMutation.isError ? "重试取消" : "取消任务"}
            cancelPending={cancelMutation.isPending || !writeReady}
            errorMessage={
              cancelMutation.isError
                ? runtimeErrorMessage(cancelMutation.error, "任务还没有取消，请检查网络后重试。")
                : jobQuery.isError
                  ? runtimeErrorMessage(jobQuery.error, "任务状态暂时无法读取，请稍后重试。")
                  : undefined
            }
            job={job}
            loading={jobQuery.isFetching}
            onCancel={writeReady && jobOwnedByProject ? () => cancelMutation.mutate() : undefined}
            onRefresh={() => void jobQuery.refetch()}
          />
        )}
        {!writeReady && jobOwnedByProject && job && !terminalStatuses.has(job.status) ? (
          <p
            className="mt-4 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] p-3 text-sm text-[var(--sh-warning)]"
            role="status"
          >
            当前会话仅支持查看进度，无法取消任务。
          </p>
        ) : null}
      </div>
    </div>
  );
}
