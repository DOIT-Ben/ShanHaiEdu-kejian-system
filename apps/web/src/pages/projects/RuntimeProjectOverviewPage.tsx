import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpenCheck, FileText, Images } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import {
  getProjectAutomationPolicyVersioned,
  updateProjectAutomationPolicy,
} from "@/features/projects/api/automationPolicyApi";
import { getProject } from "@/features/projects/api/projectsApi";
import { projectKeys } from "@/features/projects/hooks/useProjectsQuery";
import { ProjectLessonGrid } from "@/features/projects/components/ProjectOverviewContent";
import { listProjectLessons } from "@/features/lessons/api/lessonsApi";
import { isCsrfTokenAvailable } from "@/shared/api/client";
import { useProjectEvents } from "@/shared/api/useProjectEvents";
import { Button, buttonVariants } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { Select } from "@/shared/ui/Select";

const branchLabels = {
  intro_options: "课堂导入",
  lesson_plan: "教案",
  ppt: "课件后续开放",
  video: "课堂视频",
} as const;

export function RuntimeProjectOverviewPage() {
  const { projectId } = useParams();
  const queryClient = useQueryClient();
  useProjectEvents(projectId);
  const projectQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProject(projectId ?? ""),
    queryKey: projectKeys.detail(projectId ?? ""),
  });
  const policyQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => getProjectAutomationPolicyVersioned(projectId ?? ""),
    queryKey: ["projects", projectId, "automation-policy"],
  });
  const lessonsQuery = useQuery({
    enabled: Boolean(projectId),
    queryFn: () => listProjectLessons(projectId ?? ""),
    queryKey: ["projects", projectId, "lessons"],
  });
  const policyMutation = useMutation({
    mutationFn: updateProjectAutomationPolicy,
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        exact: true,
        queryKey: ["projects", projectId, "automation-policy"],
      });
    },
  });
  const writeReady = isCsrfTokenAvailable();

  if (!projectId) return null;
  if (projectQuery.isLoading) {
    return (
      <div className="mx-auto max-w-[1120px] px-4 py-8 md:px-6" role="status">
        <div className="h-36 animate-pulse rounded-[var(--sh-radius-lg)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
        <span className="sr-only">正在读取项目</span>
      </div>
    );
  }
  if (!projectQuery.data || projectQuery.isError) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-8 md:px-6">
        <FocusPageHeader
          description="项目暂时无法读取，请检查网络或返回项目列表。"
          title="没有打开这个项目"
        />
        <Link className={buttonVariants({ className: "mt-6" })} to="/app/projects">
          <ArrowLeft aria-hidden="true" />
          返回项目列表
        </Link>
      </div>
    );
  }

  const project = projectQuery.data;
  const lessonSummaries = (lessonsQuery.data?.lessons ?? []).map((lesson) => ({
    branches: lesson.branches.map((branch) => ({
      enabled: branch.enabled,
      key: branch.branch_key,
      label: branchLabels[branch.branch_key],
      to: `/app/projects/${projectId}/lessons/${lesson.id}/work/${branch.branch_key}`,
    })),
    durationMinutes: lesson.estimated_minutes ?? undefined,
    id: lesson.id,
    scope: lesson.scope_summary,
    title: lesson.title,
  }));
  return (
    <div className="mx-auto max-w-[1180px] px-4 py-5 md:px-6 lg:px-8">
      <FocusPageHeader
        action={
          <Link className={buttonVariants({ variant: "secondary" })} to="/app/projects">
            <ArrowLeft aria-hidden="true" />
            全部项目
          </Link>
        }
        description={[project.grade, project.textbook_edition, project.knowledge_point]
          .filter(Boolean)
          .join(" · ")}
        title={project.title}
      />

      <nav aria-label="项目资料" className="mt-4 flex flex-wrap gap-2">
        <Link
          className={buttonVariants({ size: "sm", variant: "secondary" })}
          to={`/app/projects/${projectId}/materials`}
        >
          <FileText aria-hidden="true" />
          教材与解析
        </Link>
        <Link
          className={buttonVariants({ size: "sm", variant: "secondary" })}
          to={`/app/projects/${projectId}/lessons`}
        >
          <BookOpenCheck aria-hidden="true" />
          编辑课时
        </Link>
        <Link
          className={buttonVariants({ size: "sm", variant: "secondary" })}
          to={`/app/projects/${projectId}/assets`}
        >
          <Images aria-hidden="true" />
          项目素材
        </Link>
      </nav>

      <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <ProjectLessonGrid
          emptyMessage="当前项目还没有课时。课时创建和教案生成暂不可用。"
          errorMessage={lessonsQuery.isError ? "课时暂时无法读取，请检查网络后重试。" : undefined}
          lessons={lessonSummaries}
          loading={lessonsQuery.isLoading}
          onRetry={() => void lessonsQuery.refetch()}
        />

        <aside className="h-fit rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 shadow-[var(--sh-shadow-card)]">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">制作方式</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--sh-ink-muted)]">
            边看边确认适合逐步调整；自动完成会继续执行当前允许的步骤。
          </p>
          <p className="mt-3 rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] p-3 text-xs leading-5 text-[var(--sh-ink-muted)]">
            课程范围已保存；教材使用情况暂时不会显示在这里。
          </p>
          <Select
            ariaLabel="选择制作方式"
            className="mt-4 w-full"
            disabled={!writeReady || !policyQuery.data?.etag || policyMutation.isPending}
            onValueChange={(mode) => {
              if (!policyQuery.data?.etag || (mode !== "guided" && mode !== "automatic")) return;
              policyMutation.mutate({
                etag: policyQuery.data.etag,
                idempotencyKey: crypto.randomUUID(),
                input: { mode },
                projectId,
              });
            }}
            options={[
              { label: "边看边确认", value: "guided" },
              { label: "自动完成可执行步骤", value: "automatic" },
            ]}
            value={policyQuery.data?.policy.mode}
          />
          {policyQuery.isError ? (
            <div className="mt-3 text-xs leading-5 text-[var(--sh-danger)]" role="alert">
              <p>制作方式暂时无法读取，请检查网络后重试。</p>
              <Button
                className="mt-3"
                onClick={() => void policyQuery.refetch()}
                size="sm"
                variant="secondary"
              >
                重新读取制作方式
              </Button>
            </div>
          ) : !writeReady ? (
            <p className="mt-3 text-xs leading-5 text-[var(--sh-warning)]" role="status">
              暂时不能修改制作方式，请刷新页面后重试。
            </p>
          ) : null}
          {policyMutation.isError ? (
            <p className="mt-3 text-xs leading-5 text-[var(--sh-danger)]" role="alert">
              制作方式没有保存，请刷新后再试。
            </p>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
