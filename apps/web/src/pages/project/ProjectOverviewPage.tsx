import { useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowRight, PauseCircle, Wallet } from "lucide-react";
import { useAuthorizeBudgetAndResume, useProjectWorkflow } from "@/features/projects";
import { getBranchStateMeta } from "@/shared/lib/status";
import { formatMinorUnits } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Skeleton,
  toast,
} from "@/shared/ui";

/** 项目总览：当前要做什么、各课时分支进度、自动执行与预算状态。 */
export default function ProjectOverviewPage() {
  const { projectId = "" } = useParams();
  const { data, isPending } = useProjectWorkflow(projectId);
  const [budgetOpen, setBudgetOpen] = useState(false);
  const authorize = useAuthorizeBudgetAndResume(projectId);

  if (isPending || !data) {
    return (
      <div className="mx-auto w-full max-w-[var(--sh-content-max)] space-y-4 px-6 py-8">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-40 rounded-lg" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const { project, lessons, material, automation } = data;
  const pendingLesson = lessons.find((lesson) =>
    Object.values(lesson.branches).some(
      (branch) => branch.state === "review_required" || branch.state === "in_progress" || branch.state === "stale",
    ),
  );
  const nextAction = !material
    ? { label: "上传教材，开始创作", to: `/app/projects/${projectId}/materials` }
    : material.status !== "scope_confirmed"
      ? { label: "确认教材范围", to: `/app/projects/${projectId}/materials` }
      : lessons.length === 0
        ? { label: "确认课时划分", to: `/app/projects/${projectId}/materials` }
        : pendingLesson
          ? {
              label: `继续「${pendingLesson.title}」`,
              to: `/app/projects/${projectId}/lessons/${pendingLesson.id}`,
            }
          : { label: "查看交付", to: `/app/projects/${projectId}/delivery` };

  const budgetPaused =
    automation?.state === "paused" && automation.paused_reason === "budget_confirmation_required";
  const estimate = automation?.pending_estimate;

  return (
    <div className="mx-auto w-full max-w-[var(--sh-content-max)] px-6 py-8">
      <PageHeader
        title={project.title}
        description={`知识点：${project.knowledge_point}${project.grade ? ` · ${project.grade}` : ""}${project.textbook_edition ? ` · ${project.textbook_edition}` : ""}`}
        actions={
          <Button asChild>
            <Link to={nextAction.to}>
              {nextAction.label}
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </Button>
        }
      />

      {budgetPaused ? (
        <div className="mt-6 flex flex-wrap items-center gap-4 rounded-lg border border-warning-200 bg-warning-50 p-5">
          <PauseCircle className="size-6 shrink-0 text-warning" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ink-strong">自动执行已暂停：等待你确认费用</p>
            <p className="mt-0.5 text-sm text-ink">
              {automation?.paused_detail ?? "下一批生成需要确认预算后才会继续。"}
              {estimate
                ? ` 预计费用 ${formatMinorUnits(estimate.minor_units)}（${estimate.summary ?? "本批生成"}）。`
                : ""}
            </p>
          </div>
          <Button onClick={() => setBudgetOpen(true)}>
            <Wallet className="size-4" aria-hidden />
            确认费用并继续
          </Button>
        </div>
      ) : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_340px]">
        <Panel>
          <PanelHeader title="课时进度" description="每个课时的教案、导入、PPT 与视频分支进展。" />
          <PanelBody className="p-0">
            {lessons.length === 0 ? (
              <p className="p-6 text-sm text-ink-muted">
                课时尚未生成。先在「教材与课时」完成教材上传与课时划分。
              </p>
            ) : (
              <ul className="divide-y divide-line-subtle">
                {lessons.map((lesson) => (
                  <li key={lesson.id}>
                    <Link
                      to={`/app/projects/${projectId}/lessons/${lesson.id}`}
                      className="flex flex-wrap items-center gap-3 px-5 py-4 transition-colors duration-150 hover:bg-surface-soft"
                    >
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-brand-50 text-xs font-semibold text-brand-600">
                        {lesson.position}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-ink-strong">{lesson.title}</span>
                        <span className="mt-0.5 block truncate text-xs text-ink-muted">{lesson.focus}</span>
                      </span>
                      <span className="flex flex-wrap items-center gap-1.5">
                        {(
                          [
                            ["教案", lesson.branches.lesson_plan],
                            ["导入", lesson.branches.intro_options],
                            ["PPT", lesson.branches.ppt],
                            ["视频", lesson.branches.video],
                          ] as const
                        ).map(([label, branch]) => {
                          const meta = getBranchStateMeta(branch.state);
                          return (
                            <Badge key={label} tone={meta.tone} title={branch.summary ?? undefined}>
                              {label}·{meta.label}
                            </Badge>
                          );
                        })}
                      </span>
                      <ArrowRight className="size-4 shrink-0 text-ink-faint" aria-hidden />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </PanelBody>
        </Panel>

        <div className="space-y-6">
          <Panel>
            <PanelHeader title="教材" />
            <PanelBody>
              {material ? (
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-muted">文件</dt>
                    <dd className="truncate font-medium text-ink-strong">{material.file_name}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-muted">范围</dt>
                    <dd className="text-right text-ink">{material.knowledge_scope ?? "待确认"}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-ink-muted">还没有上传教材。</p>
              )}
              <Button asChild variant="outline" size="sm" className="mt-4">
                <Link to={`/app/projects/${projectId}/materials`}>教材与课时</Link>
              </Button>
            </PanelBody>
          </Panel>
          {automation ? (
            <Panel>
              <PanelHeader title="费用" />
              <PanelBody>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-muted">已使用</dt>
                    <dd className="font-medium text-ink-strong">
                      {formatMinorUnits(automation.spent_minor_units ?? 0)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-ink-muted">项目预算</dt>
                    <dd className="text-ink">{formatMinorUnits(automation.budget_minor_units ?? 0)}</dd>
                  </div>
                </dl>
              </PanelBody>
            </Panel>
          ) : null}
        </div>
      </div>

      <Dialog open={budgetOpen} onOpenChange={setBudgetOpen}>
        <DialogContent title="确认费用并继续" description="确认后系统将继续自动执行，直到完成或再次需要你确认。">
          <div className="space-y-3 text-sm">
            <p className="rounded-md bg-surface-soft p-3 text-ink">
              {estimate?.summary ?? "下一批生成"}：预计{" "}
              <strong className="text-ink-strong">{formatMinorUnits(estimate?.minor_units ?? 0)}</strong>
            </p>
            <p className="text-ink-muted">
              实际费用以真实用量为准；超过确认额度时会再次暂停等待你确认。
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setBudgetOpen(false)}>
              暂不继续
            </Button>
            <Button
              loading={authorize.isPending}
              loadingText="正在恢复…"
              onClick={() =>
                authorize.mutate(
                  { maxMinorUnits: estimate?.minor_units ?? 0 },
                  {
                    onSuccess: () => {
                      setBudgetOpen(false);
                      toast({ tone: "success", title: "已确认费用", description: "自动执行已继续。" });
                    },
                    onError: (error) =>
                      toast({ tone: "danger", title: "恢复失败", description: error.message }),
                  },
                )
              }
            >
              确认 {formatMinorUnits(estimate?.minor_units ?? 0)} 并继续
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
