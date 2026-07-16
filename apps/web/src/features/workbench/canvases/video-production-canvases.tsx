import { useMemo } from "react";
import { CheckCircle2, Clapperboard, Download, FileAudio, RotateCcw } from "lucide-react";
import {
  audioSubtitleContentSchema,
  clipsContentSchema,
  finalCutContentSchema,
  parseContent,
  type Clip,
} from "@/entities/content";
import { useAssetDetail, useDownloadFile } from "@/features/assets";
import { AppError } from "@/shared/api";
import { formatDuration, formatFileSize } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, Skeleton } from "@/shared/ui";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

interface FallbackDetails {
  fallback_provider_name?: string;
  incurred_cost_minor_units?: number;
  extra_cost_minor_units?: number;
}

function ClipCard({
  clip,
  pending,
  onRetry,
  onApprove,
}: {
  clip: Clip;
  pending?: boolean;
  onRetry: () => void;
  onApprove: () => void;
}) {
  const asset = useAssetDetail(clip.video_asset_id);
  const tone =
    clip.status === "approved" ? "success" : clip.status === "failed" ? "danger" : clip.status === "generating" ? "running" : "neutral";
  const label =
    clip.status === "approved"
      ? "已批准"
      : clip.status === "failed"
        ? "失败"
        : clip.status === "generating"
          ? "生成中"
          : clip.status === "completed"
            ? "待确认"
            : "排队中";
  return (
    <div className={cn("rounded-card border bg-surface-1 p-3", clip.status === "failed" ? "border-danger/40" : "border-line")}>
      {clip.status === "generating" ? (
        <Skeleton className="aspect-video w-full" />
      ) : asset.data?.asset.thumbnail_url ? (
        <div className="relative">
          <img src={asset.data.asset.thumbnail_url} alt={`镜头${clip.shot_no}片段`} className="aspect-video w-full rounded-control object-cover" />
          <span className="absolute bottom-1.5 right-1.5 rounded-control bg-black/60 px-1.5 py-0.5 text-[10px] text-white">
            {formatDuration(clip.duration_seconds * 1000)}
          </span>
        </div>
      ) : (
        <span className="flex aspect-video items-center justify-center rounded-control bg-surface-2 text-ink-muted">
          <Clapperboard className="size-6" aria-hidden />
        </span>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-ink-1">镜头 #{clip.shot_no}</span>
        <Badge tone={tone}>{label}</Badge>
      </div>
      {clip.attempt > 1 ? <p className="mt-0.5 text-[10px] text-ink-muted">第 {clip.attempt} 次生成</p> : null}
      {clip.status === "failed" ? (
        <>
          {clip.error_message ? <p className="mt-1 text-xs leading-5 text-danger">{clip.error_message}</p> : null}
          <Button size="sm" variant="secondary" className="mt-2 w-full" onClick={onRetry} disabled={pending}>
            <RotateCcw className="size-3.5" aria-hidden />
            重试该镜头
          </Button>
        </>
      ) : clip.status === "completed" ? (
        <Button size="sm" className="mt-2 w-full" onClick={onApprove} disabled={pending}>
          <CheckCircle2 className="size-3.5" aria-hidden />
          批准此片段
        </Button>
      ) : null}
    </div>
  );
}

/** 视频片段画布：分镜头片段卡片；失败镜头单独重试（备用服务付费确认由工作台统一处理），部分成功不阻塞其余镜头。 */
export function ClipsCanvas({ workspace, onItemAction, itemActionPending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(clipsContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="视频片段" />;

  const failed = content.clips.filter((clip) => clip.status === "failed").length;
  const done = content.clips.filter((clip) => clip.status === "approved" || clip.status === "completed").length;

  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">
        共 {content.clips.length} 个镜头，完成 {done} 个
        {failed > 0 ? <span className="text-warning">，失败 {failed} 个（可单独重试，已完成镜头不受影响）</span> : null}
      </p>
      <div className="grid gap-3 xl:grid-cols-4 lg:grid-cols-3 md:grid-cols-2">
        {content.clips.map((clip) => (
          <ClipCard
            key={clip.clip_id}
            clip={clip}
            pending={itemActionPending}
            onRetry={() => onItemAction({ itemId: clip.clip_id, action: "retry_clip" })}
            onApprove={() => onItemAction({ itemId: clip.clip_id, action: "approve_clip" })}
          />
        ))}
      </div>
    </div>
  );
}

/** 供工作台捕获 409 PROVIDER_FALLBACK_CONFIRMATION_REQUIRED 后回调打开确认框。 */
export function extractFallbackDetails(error: unknown): FallbackDetails | null {
  if (error instanceof AppError && error.code === "PROVIDER_FALLBACK_CONFIRMATION_REQUIRED") {
    return (error.details ?? {}) as FallbackDetails;
  }
  return null;
}

/** 声音与字幕画布。 */
export function AudioSubtitleCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(audioSubtitleContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const download = useDownloadFile();
  const subtitleAsset = useAssetDetail(content?.subtitle_asset_id ?? null);
  if (!content) return <InvalidContent nodeTitle="声音字幕" />;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 rounded-card border border-line bg-surface-1 p-4">
        <FileAudio className="size-6 text-brand" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-ink-1">配音：{content.voice_name}</p>
          <p className="text-xs text-ink-muted">{content.segments.length} 段字幕已对齐</p>
        </div>
        {content.subtitle_asset_id ? (
          <Button
            variant="secondary"
            size="sm"
            loading={download.isPending}
            onClick={() => {
              const fileObjectId = subtitleAsset.data?.versions[0]?.file_object?.file_object_id;
              if (fileObjectId) download.mutate({ fileObjectId });
            }}
          >
            <Download className="size-4" aria-hidden />
            下载字幕
          </Button>
        ) : null}
      </div>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-muted">
            <th className="w-32 py-1.5 pr-3 font-medium">时间</th>
            <th className="py-1.5 font-medium">字幕</th>
          </tr>
        </thead>
        <tbody>
          {content.segments.map((segment, index) => (
            <tr key={index} className="border-b border-divider">
              <td className="py-2 pr-3 font-mono text-xs text-ink-muted">
                {segment.start_seconds}s – {segment.end_seconds}s
              </td>
              <td className="py-2 leading-6 text-ink-2">{segment.text}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** 剪辑成片画布：成片预览信息 + 下载。 */
export function FinalCutCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(finalCutContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const asset = useAssetDetail(content?.video_asset_id ?? null);
  const download = useDownloadFile();
  if (!content) return <InvalidContent nodeTitle="剪辑成片" />;
  const fileObject = asset.data?.versions[0]?.file_object ?? null;
  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-card border border-line bg-surface-1">
        {asset.data?.asset.thumbnail_url ? (
          <img src={asset.data.asset.thumbnail_url} alt="成片封面帧" className="aspect-video w-full object-cover" />
        ) : (
          <span className="flex aspect-video items-center justify-center bg-surface-2 text-ink-muted">
            <Clapperboard className="size-8" aria-hidden />
          </span>
        )}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-4 py-3 text-xs text-ink-2">
          <span>时长 {formatDuration(content.duration_seconds * 1000)}</span>
          <span>{content.resolution}</span>
          <span>{formatFileSize(content.size_bytes)}</span>
          <span>包含 {content.included_shot_ids.length} 个镜头</span>
          <Button
            size="sm"
            className="ml-auto"
            loading={download.isPending}
            disabled={!fileObject}
            onClick={() => {
              if (fileObject) download.mutate({ fileObjectId: fileObject.file_object_id, fileName: fileObject.file_name });
            }}
          >
            <Download className="size-4" aria-hidden />
            下载成片
          </Button>
        </div>
      </div>
    </div>
  );
}
