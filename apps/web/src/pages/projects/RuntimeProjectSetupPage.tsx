import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, BookOpen, CheckCircle2, LoaderCircle, XCircle } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { cancelGenerationJob, getGenerationJob } from "@/features/jobs/api/jobsApi";
import { listProjectLessons } from "@/features/lessons/api/lessonsApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { useJobEvents } from "@/shared/api/useJobEvents";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";

const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function RuntimeProjectSetupPage() {
  const { projectId } = useParams();
  const [searchParams] = useSearchParams();
  const jobId = searchParams.get("jobId") ?? undefined;
  const queryClient = useQueryClient();
  useJobEvents(jobId, projectId);

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
      const status = query.state.data?.status;
      return status && terminalStatuses.has(status) ? false : 5_000;
    },
  });
  const lessonsQuery = useQuery({
    enabled: Boolean(projectId) && jobQuery.data?.status === "succeeded",
    queryFn: () => listProjectLessons(projectId ?? ""),
    queryKey: ["projects", projectId, "lessons"],
  });
  const cancelMutation = useMutation({
    mutationFn: cancelGenerationJob,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["generation-jobs", jobId], exact: true });
    },
  });

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

  const job = jobQuery.data;
  const progress = Math.min(100, Math.max(0, job?.progress_percent ?? 0));
  const running = job && !terminalStatuses.has(job.status);
  const writeReady = isCsrfTokenAvailable();
  return (
    <div className="mx-auto max-w-[980px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        description="教材会在后台解析。你可以离开页面，稍后再回来查看。"
        title={projectQuery.data?.title ?? "正在准备课堂项目"}
      />
      <section className="mt-5 overflow-hidden rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-card)]">
        <div className="grid gap-4 p-5 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center">
          <span
            className={
              job?.status === "succeeded"
                ? "grid size-12 place-items-center rounded-full bg-[var(--sh-success-soft)] text-[var(--sh-success)]"
                : job?.status === "failed" || job?.status === "cancelled"
                  ? "grid size-12 place-items-center rounded-full bg-[var(--sh-danger-soft)] text-[var(--sh-danger)]"
                  : "grid size-12 place-items-center rounded-full bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]"
            }
          >
            {job?.status === "succeeded" ? (
              <CheckCircle2 aria-hidden="true" className="size-6" />
            ) : job?.status === "failed" || job?.status === "cancelled" ? (
              <XCircle aria-hidden="true" className="size-6" />
            ) : (
              <LoaderCircle
                aria-hidden="true"
                className="size-6 animate-spin motion-reduce:animate-none"
              />
            )}
          </span>
          <div>
            <h2 className="font-semibold text-[var(--sh-ink-strong)]">
              {job?.status === "succeeded"
                ? "教材已经准备好"
                : job?.status === "failed"
                  ? "教材解析没有完成"
                  : job?.status === "cancelled"
                    ? "教材任务已取消"
                    : "正在读取教材内容"}
            </h2>
            <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">
              {job?.progress_message ??
                (jobQuery.isError ? "暂时无法读取进度，请检查网络后重试。" : "正在等待服务端更新")}
            </p>
          </div>
          {running ? (
            <Button
              disabled={cancelMutation.isPending || !writeReady}
              onClick={() => cancelMutation.mutate({ idempotencyKey: crypto.randomUUID(), jobId })}
              variant="secondary"
            >
              {cancelMutation.isPending
                ? "正在取消"
                : cancelMutation.isError
                  ? "重试取消"
                  : "取消任务"}
            </Button>
          ) : null}
        </div>
        <div className="h-2 bg-[var(--sh-surface-soft)]">
          <div
            aria-label={"教材处理进度 " + String(progress) + "%"}
            aria-valuemax={100}
            aria-valuemin={0}
            aria-valuenow={progress}
            className="h-full rounded-r-full bg-[image:var(--sh-action-gradient)] transition-[width] duration-[var(--sh-duration-normal)] motion-reduce:transition-none"
            role="progressbar"
            style={{ width: String(progress) + "%" }}
          />
        </div>
        {cancelMutation.isError ? (
          <p
            className="border-t border-[var(--sh-line-subtle)] px-5 py-3 text-sm text-[var(--sh-danger)]"
            role="alert"
          >
            任务还没有取消，请检查网络后重试。正在处理的内容不会丢失。
          </p>
        ) : null}
        {running && !writeReady ? (
          <p
            className="border-t border-[var(--sh-line-subtle)] px-5 py-3 text-xs text-[var(--sh-warning)]"
            role="status"
          >
            安全会话尚未就绪，暂时不能取消任务。请刷新后重试。
          </p>
        ) : null}
      </section>

      {job?.status === "succeeded" ? (
        <section className="mt-4 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
          <div className="flex items-center gap-2 text-[var(--sh-brand-700)]">
            <BookOpen aria-hidden="true" className="size-5" />
            <h2 className="font-semibold">下一步，确认课时</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
            {lessonsQuery.data?.lessons.length
              ? "系统已经整理出 " + String(lessonsQuery.data.lessons.length) + " 个课时。"
              : lessonsQuery.isLoading
                ? "正在读取课时建议。"
                : "课时建议还在准备，请稍后刷新。"}
          </p>
          <Link className={buttonVariants() + " mt-4"} to={"/app/projects/" + projectId}>
            查看项目
            <ArrowRight aria-hidden="true" />
          </Link>
        </section>
      ) : null}
    </div>
  );
}
