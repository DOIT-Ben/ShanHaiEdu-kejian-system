import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen } from "lucide-react";
import { useRef } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  cancelGenerationJob,
  getGenerationJob,
  type GenerationJobDto,
} from "@/features/jobs/api/jobsApi";
import { GenerationJobPanel } from "@/features/jobs/components/GenerationJobPanel";
import { listProjectLessons } from "@/features/lessons/api/lessonsApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { runtimeErrorMessage } from "@/shared/api/runtimeError";
import { useJobEvents } from "@/shared/api/useJobEvents";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const terminalStatuses = new Set<GenerationJobDto["status"]>(["succeeded", "failed", "cancelled"]);

function setupStatusTitle(status: GenerationJobDto["status"] | undefined) {
  if (status === "succeeded") return "教材已经准备好";
  if (status === "failed") return "教材解析没有完成";
  if (status === "cancelled") return "教材任务已取消";
  return "正在读取教材内容";
}

export function RuntimeProjectSetupPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const jobId = searchParams.get("jobId") ?? undefined;
  const materialId = searchParams.get("materialId") ?? undefined;
  const queryClient = useQueryClient();
  const cancelIntentRef = useRef<Parameters<typeof cancelGenerationJob>[0] | null>(null);

  const projectQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProject(projectId ?? ""),
    queryKey: projectKeys.detail(projectId ?? ""),
  });
  const jobQuery = useQuery({
    enabled: Boolean(jobId),
    queryFn: () => getGenerationJob(jobId ?? ""),
    queryKey: ["generation-jobs", jobId],
    refetchInterval: (query) => {
      const job = query.state.data;
      if (job && job.project_id !== projectId) return false;
      const status = job?.status;
      return status && terminalStatuses.has(status) ? false : 5_000;
    },
  });
  const job = jobQuery.data;
  const jobOwnedByProject = Boolean(projectId && job?.project_id === projectId);
  const jobNeedsLiveUpdates = Boolean(
    jobOwnedByProject && job && !terminalStatuses.has(job.status),
  );
  useJobEvents(
    jobNeedsLiveUpdates ? jobId : undefined,
    jobNeedsLiveUpdates ? projectId : undefined,
  );

  const lessonsQuery = useQuery({
    enabled: jobOwnedByProject && job?.status === "succeeded",
    queryFn: () => listProjectLessons(projectId ?? ""),
    queryKey: ["projects", projectId, "lessons"],
  });
  const cancelMutation = useMutation({
    mutationFn: (input: Parameters<typeof cancelGenerationJob>[0]) => {
      if (job?.project_id !== projectId) {
        throw new Error("GENERATION_JOB_CANCEL_NOT_ALLOWED");
      }
      return cancelGenerationJob(input);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["generation-jobs", jobId], exact: true });
    },
  });
  const requestCancellation = () => {
    if (!jobId) return;
    const currentIntent = cancelIntentRef.current;
    const cancelIntent =
      currentIntent?.jobId === jobId
        ? currentIntent
        : { idempotencyKey: crypto.randomUUID(), jobId };
    cancelIntentRef.current = cancelIntent;
    cancelMutation.mutate(cancelIntent);
  };

  if (!projectId || !jobId) {
    return (
      <div className="mx-auto max-w-[880px] px-4 py-8 md:px-6">
        <FocusPageHeader
          description="没有找到可恢复的教材任务，请回到项目列表重新进入。"
          title="无法读取项目进度"
        />
        <Link className={buttonVariants() + " mt-6"} to="/app/projects">
          返回项目列表
        </Link>
      </div>
    );
  }

  if (job && !jobOwnedByProject) {
    return (
      <div className="mx-auto max-w-[880px] px-4 py-8 md:px-6">
        <FocusPageHeader
          description="请返回当前项目，从教材任务入口重新进入。"
          title="教材进度暂时无法打开"
        />
        <Link
          className={buttonVariants({ className: "mt-6", variant: "secondary" })}
          to={`/app/projects/${projectId}`}
        >
          返回项目
        </Link>
      </div>
    );
  }

  const running = jobOwnedByProject && job && !terminalStatuses.has(job.status);
  const writeReady = isCsrfTokenAvailable();
  const lessonCount = lessonsQuery.data?.lessons.length ?? 0;
  const hasLessons = lessonCount > 0;
  return (
    <div className="mx-auto max-w-[980px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        description="教材会在后台解析。你可以离开页面，稍后再回来查看。"
        title={projectQuery.data?.title ?? "正在准备课堂项目"}
      />
      <div className="mt-5 shadow-[var(--sh-shadow-card)]">
        <GenerationJobPanel
          cancelLabel={cancelMutation.isError ? "重试取消" : "取消任务"}
          cancelPending={cancelMutation.isPending || !writeReady}
          errorMessage={
            cancelMutation.isError
              ? "任务还没有取消，请检查网络后重试。正在处理的内容不会丢失。"
              : jobQuery.isError
                ? runtimeErrorMessage(jobQuery.error, "暂时无法读取进度，请检查网络后重试。")
                : undefined
          }
          job={job}
          loading={jobQuery.isFetching}
          onCancel={running ? requestCancellation : undefined}
          onRefresh={() => void jobQuery.refetch()}
          progressLabel="教材处理进度"
          title={setupStatusTitle(job?.status)}
        />
        {running && !writeReady ? (
          <p
            className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-warning-soft)] px-5 py-3 text-xs text-[var(--sh-warning)]"
            role="status"
          >
            当前会话只能查看任务进度，暂时无法取消任务。
          </p>
        ) : null}
      </div>

      {job?.status === "succeeded" ? (
        <section className="mt-4 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
          <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
            <BookOpen aria-hidden="true" className="size-5" />
            <h2 className="font-semibold">
              {lessonsQuery.isLoading
                ? "正在读取已有课时"
                : lessonsQuery.isError
                  ? "课时暂时无法读取"
                  : hasLessons
                    ? "课时已经可以核对"
                    : "课时尚未建立"}
            </h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
            {lessonsQuery.isLoading
              ? "教材解析已完成，正在读取项目中已有的课时。"
              : lessonsQuery.isError
                ? "教材解析已完成，但暂时无法读取课时。请重新读取，或先返回项目查看已保存内容。"
                : hasLessons
                  ? `项目中已经保存 ${String(lessonCount)} 个课时，可以进入课时页核对和编辑。`
                  : "教材解析已完成，但当前项目还没有课时。课时创建和教案生成暂不可用，请返回项目查看已保存内容。"}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {hasLessons ? (
              <Link className={buttonVariants()} to={`/app/projects/${projectId}/lessons`}>
                查看课时
                <ArrowRight aria-hidden="true" />
              </Link>
            ) : (
              <Link className={buttonVariants()} to={`/app/projects/${projectId}`}>
                返回项目
              </Link>
            )}
            {lessonsQuery.isError ? (
              <Button onClick={() => void lessonsQuery.refetch()} variant="secondary">
                重新读取课时
              </Button>
            ) : null}
            {materialId ? (
              <Link
                className={buttonVariants({ variant: "secondary" })}
                to={`/app/projects/${projectId}/materials/${encodeURIComponent(materialId)}`}
              >
                查看教材详情
              </Link>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
