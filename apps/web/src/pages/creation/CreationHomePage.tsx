import { Link } from "react-router";
import { ArrowRight, Images, Presentation, Video } from "lucide-react";
import { useBatches } from "@/features/creation";
import { formatRelativeTime } from "@/shared/lib/format";
import { Badge, PageHeader, Skeleton } from "@/shared/ui";

const STUDIOS = [
  {
    key: "image",
    icon: Images,
    title: "制作图片",
    description: "教学插图、示意图、场景图——描述想要的画面即可。",
    route: "/app/creation/images",
  },
  {
    key: "video",
    icon: Video,
    title: "制作视频",
    description: "从参考画面出发，说清楚画面怎样变化、镜头持续多久。",
    route: "/app/creation/videos",
  },
  {
    key: "presentation",
    icon: Presentation,
    title: "制作 PPT 页面",
    description: "单页或补充页面；先确定风格再制作正文。",
    route: "/app/creation/presentations",
  },
] as const;

const BATCH_STATUS_LABELS: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "warning" }> = {
  draft: { label: "准备中", tone: "neutral" },
  ready: { label: "待生成", tone: "brand" },
  running: { label: "生成中", tone: "running" },
  partially_completed: { label: "部分完成", tone: "warning" },
  completed: { label: "已完成", tone: "success" },
  archived: { label: "已归档", tone: "neutral" },
};

/** 创作中心首页（03 §1）：今天想创作什么 + 最近批次。 */
export default function CreationHomePage() {
  const { data: batches, isPending } = useBatches();

  return (
    <div className="mx-auto w-full max-w-[var(--sh-content-max)] px-6 py-8">
      <PageHeader
        title="今天想创作什么？"
        description="独立制作图片、视频或 PPT 页面；满意的结果可以保存到任何项目。"
      />
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {STUDIOS.map((studio) => (
          <Link
            key={studio.key}
            to={studio.route}
            className="group rounded-lg border border-line-subtle bg-surface p-6 shadow-card transition-shadow duration-150 hover:shadow-floating"
          >
            <studio.icon className="size-8 text-brand-500" aria-hidden />
            <h2 className="mt-4 flex items-center gap-1.5 text-base font-semibold text-ink-strong">
              {studio.title}
              <ArrowRight
                className="size-4 text-ink-faint transition-transform duration-150 group-hover:translate-x-0.5"
                aria-hidden
              />
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-muted">{studio.description}</p>
          </Link>
        ))}
      </div>

      <section className="mt-10" aria-label="最近的创作">
        <h2 className="text-base font-semibold text-ink-strong">最近的创作</h2>
        {isPending ? (
          <div className="mt-4 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        ) : batches && batches.length > 0 ? (
          <ul className="mt-4 space-y-3">
            {batches.map((batch) => {
              const meta = BATCH_STATUS_LABELS[batch.status] ?? { label: batch.status, tone: "neutral" as const };
              return (
                <li key={batch.id}>
                  <Link
                    to={`/app/creation/batches/${batch.id}`}
                    className="flex flex-wrap items-center gap-3 rounded-lg border border-line-subtle bg-surface px-5 py-4 transition-colors duration-150 hover:bg-surface-soft"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink-strong">{batch.title}</span>
                      <span className="mt-0.5 block text-xs text-ink-muted">
                        {batch.items.length} 项
                        {batch.source_project_title ? ` · 来自「${batch.source_project_title}」` : " · 独立创作"}
                        {batch.updated_at ? ` · ${formatRelativeTime(batch.updated_at)}` : ""}
                      </span>
                    </span>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    <ArrowRight className="size-4 shrink-0 text-ink-faint" aria-hidden />
                  </Link>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="mt-4 rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
            还没有创作记录。选择上面的入口开始。
          </p>
        )}
      </section>
    </div>
  );
}
