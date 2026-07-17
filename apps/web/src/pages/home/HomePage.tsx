import { Link, useNavigate } from "react-router";
import {
  ArrowRight,
  BookOpenText,
  Clapperboard,
  FileUp,
  Presentation,
  Sparkles,
} from "lucide-react";
import { useHomeOverview } from "@/features/home";
import { useCurrentUser } from "@/app/session";
import { formatRelativeTime } from "@/shared/lib/format";
import { Button, EmptyState, Skeleton, TaskStatusBadge } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

/**
 * 品牌主页「山海创作空间」（01 §3）：
 * 品牌区（hero）+ 智能入口 + 继续上次创作 + 三张能力卡 + 最近成果 + 待处理。
 */
export default function HomePage() {
  const user = useCurrentUser();
  const { data, isPending } = useHomeOverview();
  const navigate = useNavigate();

  const firstContinue = data?.continue_items[0] ?? null;

  return (
    <div className="pb-16">
      {/* 品牌区 */}
      <section className="sh-hero-gradient sh-mountain-texture">
        <div className="mx-auto flex min-h-[380px] max-w-[var(--sh-content-max)] flex-col justify-center px-6 py-14">
          <p className="text-sm font-medium text-brand-600">山海创作空间 · 欢迎回来，{user.name}</p>
          <h1 className="mt-3 max-w-2xl text-4xl font-semibold leading-tight text-ink-strong">
            把一份教材，变成完整的课堂作品
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-ink-muted">
            教案、课堂导入、PPT、导入视频——从上传教材开始，每一步都由你确认。
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            {firstContinue ? (
              <>
                <Button size="lg" onClick={() => void navigate(firstContinue.next_url)}>
                  继续上次创作
                  <ArrowRight className="size-4" aria-hidden />
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link to="/app/projects/new">
                    <FileUp className="size-4" aria-hidden />
                    上传教材，创建项目
                  </Link>
                </Button>
              </>
            ) : (
              <Button size="lg" asChild>
                <Link to="/app/projects/new">
                  <FileUp className="size-4" aria-hidden />
                  上传教材，创建项目
                </Link>
              </Button>
            )}
          </div>
          {firstContinue ? (
            <button
              type="button"
              onClick={() => void navigate(firstContinue.next_url)}
              className="mt-8 flex w-full max-w-xl items-center gap-4 rounded-lg border border-line-subtle bg-surface/90 p-4 text-left shadow-card transition-shadow hover:shadow-floating"
            >
              {firstContinue.cover_asset_url ? (
                <img
                  src={firstContinue.cover_asset_url}
                  alt=""
                  className="h-16 w-24 shrink-0 rounded-md object-cover"
                />
              ) : (
                <span className="flex h-16 w-24 shrink-0 items-center justify-center rounded-md bg-brand-50 text-brand-500">
                  <BookOpenText className="size-6" aria-hidden />
                </span>
              )}
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-ink-strong">
                  {firstContinue.project_title}
                  {firstContinue.lesson_title ? ` · ${firstContinue.lesson_title}` : ""}
                </span>
                <span className="mt-1 block truncate text-sm text-ink-muted">
                  下一步：{firstContinue.next_action}
                </span>
              </span>
              <ArrowRight className="size-4 shrink-0 text-ink-faint" aria-hidden />
            </button>
          ) : null}
        </div>
      </section>

      <div className="mx-auto max-w-[var(--sh-content-max)] space-y-12 px-6 pt-12">
        {/* 智能入口 + 能力卡 */}
        <section aria-labelledby="capability-title">
          <h2 id="capability-title" className="text-lg font-semibold text-ink-strong">
            今天想制作什么？
          </h2>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            {[
              {
                icon: BookOpenText,
                title: "从教材开始",
                description: "上传教材，自动完成课时划分与教案初稿",
                to: "/app/projects/new",
                action: "创建项目",
              },
              {
                icon: Presentation,
                title: "制作课堂 PPT",
                description: "从已批准教案生成大纲、封面与可编辑正文",
                to: "/app/projects",
                action: "选择项目",
              },
              {
                icon: Clapperboard,
                title: "制作导入视频",
                description: "三类九套创意，选一套拍成课堂导入短片",
                to: "/app/projects",
                action: "选择项目",
              },
            ].map((card) => (
              <Link
                key={card.title}
                to={card.to}
                className="group flex flex-col rounded-lg border border-line-subtle bg-surface p-6 shadow-card transition-shadow duration-150 hover:shadow-floating"
              >
                <span className="flex size-10 items-center justify-center rounded-md bg-brand-50 text-brand-600">
                  <card.icon className="size-5" aria-hidden />
                </span>
                <span className="mt-4 text-base font-semibold text-ink-strong">{card.title}</span>
                <span className="mt-1.5 flex-1 text-sm leading-relaxed text-ink-muted">
                  {card.description}
                </span>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-brand-600">
                  {card.action}
                  <ArrowRight
                    className="size-3.5 transition-transform duration-150 group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </span>
              </Link>
            ))}
          </div>
        </section>

        <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
          {/* 最近成果 */}
          <section aria-labelledby="recent-title" className="min-w-0">
            <div className="flex items-center justify-between">
              <h2 id="recent-title" className="text-lg font-semibold text-ink-strong">
                最近成果
              </h2>
              <Link to="/app/projects" className="text-sm font-medium text-brand-600 hover:underline">
                全部项目
              </Link>
            </div>
            {isPending ? (
              <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-40 rounded-lg" />
                ))}
              </div>
            ) : data && data.recent_artifacts.length > 0 ? (
              <ul className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {data.recent_artifacts.map((artifact) => (
                  <li key={artifact.id}>
                    <Link
                      to={artifact.url ?? "/app/projects"}
                      className="group block overflow-hidden rounded-lg border border-line-subtle bg-surface shadow-card transition-shadow duration-150 hover:shadow-floating"
                    >
                      {artifact.preview_url ? (
                        <img src={artifact.preview_url} alt="" className="aspect-video w-full object-cover" />
                      ) : (
                        <div className="flex aspect-video items-center justify-center bg-surface-soft text-ink-faint">
                          <Sparkles className="size-6" aria-hidden />
                        </div>
                      )}
                      <div className="p-3">
                        <p className="truncate text-sm font-medium text-ink-strong">{artifact.title}</p>
                        <p className="mt-0.5 truncate text-xs text-ink-muted">{artifact.project_title}</p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                className="mt-4"
                title="还没有成果"
                description="从上传教材开始，完成的作品会出现在这里。"
                action={
                  <Button asChild variant="secondary">
                    <Link to="/app/projects/new">上传教材，创建项目</Link>
                  </Button>
                }
              />
            )}
          </section>

          {/* 待处理 */}
          <section aria-labelledby="pending-title">
            <h2 id="pending-title" className="text-lg font-semibold text-ink-strong">
              待处理
            </h2>
            {isPending ? (
              <div className="mt-4 space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 rounded-md" />
                ))}
              </div>
            ) : data && data.pending_actions.length > 0 ? (
              <ul className="mt-4 space-y-3">
                {data.pending_actions.map((action, index) => (
                  <li key={`${action.kind}-${index}`}>
                    <button
                      type="button"
                      onClick={() => void navigate(action.url)}
                      className={cn(
                        "flex w-full items-start gap-3 rounded-md border bg-surface p-3.5 text-left transition-colors duration-150",
                        action.kind === "shot_failed" || action.kind === "budget_pause"
                          ? "border-warning-200 hover:bg-warning-50"
                          : "border-line-subtle hover:bg-surface-soft",
                      )}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium text-ink-strong">{action.title}</span>
                        {action.detail ? (
                          <span className="mt-0.5 line-clamp-2 block text-xs leading-relaxed text-ink-muted">
                            {action.detail}
                          </span>
                        ) : null}
                        {action.occurred_at ? (
                          <span className="mt-1 block text-xs text-ink-faint">
                            {formatRelativeTime(action.occurred_at)}
                          </span>
                        ) : null}
                      </span>
                      <ArrowRight className="mt-0.5 size-4 shrink-0 text-ink-faint" aria-hidden />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 rounded-md border border-dashed border-line bg-surface-soft p-4 text-sm text-ink-muted">
                暂无需要你处理的事项。
              </p>
            )}
            {data && data.running_jobs.length > 0 ? (
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-ink-strong">进行中的任务</h3>
                <ul className="mt-2 space-y-2">
                  {data.running_jobs.slice(0, 4).map((job) => (
                    <li
                      key={job.id}
                      className="flex items-center justify-between gap-2 rounded-md border border-line-subtle bg-surface px-3 py-2.5"
                    >
                      <span className="min-w-0 truncate text-sm text-ink">{job.title}</span>
                      <TaskStatusBadge status={job.status} />
                    </li>
                  ))}
                </ul>
                <Link to="/app/tasks" className="mt-2 inline-block text-sm font-medium text-brand-600 hover:underline">
                  查看任务中心
                </Link>
              </div>
            ) : null}
          </section>
        </div>
      </div>
    </div>
  );
}
