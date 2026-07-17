import { useState } from "react";
import { Link, useParams } from "react-router";
import { Download, Images, Presentation, ScrollText, Video } from "lucide-react";
import { useDownloadAssetVersion, useProjectAssets } from "@/features/assets";
import { useLessons } from "@/features/projects";
import { formatDateTime } from "@/shared/lib/format";
import { Badge, Button, EmptyState, PageHeader, Skeleton, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

/**
 * 素材与成果（04 §1）：顶部三张成果卡（教案/PPT/课堂导入视频，
 * 三类九套是教案附件不单列），下方素材筛选网格。
 */

const KIND_FILTERS = [
  { key: "all", label: "全部" },
  { key: "image", label: "教学图片" },
  { key: "ppt_page", label: "PPT 页面" },
  { key: "video_clip", label: "视频镜头" },
  { key: "audio", label: "音频字幕" },
  { key: "document", label: "文档" },
] as const;

const SUMMARY_ICONS = {
  lesson_plan: ScrollText,
  ppt: Presentation,
  video: Video,
} as const;

export default function ProjectResultsPage() {
  const { projectId = "" } = useParams();
  const [kind, setKind] = useState<string>("all");
  const [lessonId, setLessonId] = useState<string>("");
  const { data, isPending } = useProjectAssets(projectId, {
    kind,
    ...(lessonId ? { lesson_id: lessonId } : {}),
  });
  const { data: lessons } = useLessons(projectId);
  const download = useDownloadAssetVersion();

  return (
    <div className="mx-auto w-full max-w-[var(--sh-content-max)] px-6 py-8">
      <PageHeader title="素材与成果" description="课堂上直接使用的三样成果，以及制作过程中的全部素材。" />

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {(data?.summary_cards ?? []).map((card) => {
          const Icon = SUMMARY_ICONS[card.kind];
          return (
            <Link
              key={card.kind}
              to={
                card.lesson_id
                  ? `/app/projects/${projectId}/lessons/${card.lesson_id}`
                  : `/app/projects/${projectId}/lessons`
              }
              className="flex items-center gap-4 rounded-lg border border-line-subtle bg-surface p-5 shadow-card transition-shadow duration-150 hover:shadow-floating"
            >
              {card.preview_url ? (
                <img src={card.preview_url} alt="" className="h-16 w-24 shrink-0 rounded-md object-cover" />
              ) : (
                <span className="flex h-16 w-24 shrink-0 items-center justify-center rounded-md bg-brand-50">
                  <Icon className="size-6 text-brand-500" aria-hidden />
                </span>
              )}
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink-strong">{card.title}</span>
                <span className="mt-1 block text-xs text-ink-muted">{card.status}</span>
              </span>
            </Link>
          );
        })}
      </div>

      <div className="mt-8 flex flex-wrap items-center gap-2">
        <div role="tablist" aria-label="素材类型" className="flex flex-wrap gap-1 rounded-lg bg-surface-soft p-1">
          {KIND_FILTERS.map((filter) => (
            <button
              key={filter.key}
              role="tab"
              aria-selected={kind === filter.key}
              onClick={() => setKind(filter.key)}
              className={cn(
                "rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                kind === filter.key ? "bg-surface text-ink-strong shadow-sm" : "text-ink-muted hover:text-ink-strong",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <select
          aria-label="按课时筛选"
          value={lessonId}
          onChange={(e) => setLessonId(e.target.value)}
          className="ml-auto h-9 rounded-md border border-line bg-surface px-2.5 text-sm text-ink"
        >
          <option value="">全部课时</option>
          {(lessons ?? []).map((lesson) => (
            <option key={lesson.id} value={lesson.id}>
              {lesson.title}
            </option>
          ))}
        </select>
      </div>

      {isPending ? (
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      ) : data && data.items.length > 0 ? (
        <ul className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {data.items.map((asset) => (
            <li key={asset.id} className="overflow-hidden rounded-lg border border-line-subtle bg-surface shadow-card">
              <div className="aspect-video bg-surface-soft">
                {asset.preview_url ? (
                  <img src={asset.preview_url} alt={asset.title} className="size-full object-cover" />
                ) : (
                  <div className="flex size-full items-center justify-center text-ink-faint">
                    <Images className="size-8" aria-hidden />
                  </div>
                )}
              </div>
              <div className="p-3">
                <p className="truncate text-sm font-medium text-ink-strong">{asset.title}</p>
                <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-ink-muted">
                  {asset.usage_label ? <Badge tone="neutral">{asset.usage_label}</Badge> : null}
                  {asset.lesson_title ? <span>{asset.lesson_title}</span> : null}
                  <span>{formatDateTime(asset.created_at)}</span>
                </p>
                <div className="mt-2 flex items-center justify-between">
                  {asset.is_current ? <Badge tone="success">当前使用</Badge> : <span />}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      download.mutate(asset.id, {
                        onSuccess: (result) => window.open(result.url, "_blank", "noopener"),
                        onError: (error) => toast({ tone: "danger", title: "下载失败", description: error.message }),
                      })
                    }
                  >
                    <Download className="size-4" aria-hidden />
                    下载
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          className="mt-5"
          title="还没有素材"
          description="开始创作后，生成并采用的图片、页面、镜头会汇总到这里。"
        />
      )}
    </div>
  );
}
