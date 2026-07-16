import { useMemo, useState } from "react";
import { ImageIcon, Replace, RotateCcw } from "lucide-react";
import {
  fineStoryboardContentSchema,
  imageAssetsContentSchema,
  parseContent,
  roughStoryboardContentSchema,
  shotPromptsContentSchema,
} from "@/entities/content";
import { useAssetDetail } from "@/features/assets";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, Skeleton } from "@/shared/ui";
import { AssetPicker } from "@/widgets";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

/** 粗分镜画布：镜头表（场景/描述/机位/时长/旁白）。 */
export function RoughStoryboardCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(roughStoryboardContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="粗分镜" />;
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-ink-muted">
          <th className="py-2 pr-3 font-medium">镜头</th>
          <th className="py-2 pr-3 font-medium">场景</th>
          <th className="py-2 pr-3 font-medium">画面描述</th>
          <th className="py-2 pr-3 font-medium">机位</th>
          <th className="py-2 pr-3 font-medium">时长</th>
          <th className="py-2 font-medium">旁白</th>
        </tr>
      </thead>
      <tbody>
        {content.shots.map((shot) => (
          <tr key={shot.shot_id} className="border-b border-divider align-top">
            <td className="py-2.5 pr-3 font-medium text-ink-1">#{shot.shot_no}</td>
            <td className="py-2.5 pr-3 whitespace-nowrap text-ink-2">{shot.scene_title}</td>
            <td className="py-2.5 pr-3 leading-6 text-ink-2">{shot.description}</td>
            <td className="py-2.5 pr-3 whitespace-nowrap text-ink-muted">{shot.camera}</td>
            <td className="py-2.5 pr-3 whitespace-nowrap text-ink-muted">{shot.duration_seconds}s</td>
            <td className="py-2.5 leading-6 text-ink-muted">{shot.narration}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ImageAssetCard({
  item,
  pending,
  onRegenerate,
}: {
  item: { image_id: string; asset_id: string | null; shot_ids: string[]; prompt_summary: string; status: string; error_message: string | null };
  pending?: boolean;
  onRegenerate: () => void;
}) {
  const asset = useAssetDetail(item.asset_id);
  return (
    <figure
      className={cn(
        "overflow-hidden rounded-card border bg-surface-1",
        item.status === "failed" ? "border-danger/40" : "border-line",
      )}
    >
      {item.status === "generating" ? (
        <Skeleton className="aspect-video w-full" />
      ) : asset.data?.asset.thumbnail_url ? (
        <img src={asset.data.asset.thumbnail_url} alt={item.prompt_summary} className="aspect-video w-full object-cover" />
      ) : (
        <span className="flex aspect-video items-center justify-center bg-surface-2 text-ink-muted">
          <ImageIcon className="size-6" aria-hidden />
        </span>
      )}
      <figcaption className="space-y-1.5 p-3">
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-ink-muted">用于镜头 {item.shot_ids.map((id) => `#${id.replace("shot_", "")}`).join("、")}</span>
          <Badge
            tone={
              item.status === "completed" ? "success" : item.status === "failed" ? "danger" : item.status === "generating" ? "running" : "neutral"
            }
          >
            {item.status === "completed" ? "已生成" : item.status === "failed" ? "失败" : item.status === "generating" ? "生成中" : "待生成"}
          </Badge>
        </div>
        <p className="line-clamp-2 text-xs leading-5 text-ink-2">{item.prompt_summary}</p>
        {item.status === "failed" ? (
          <>
            {item.error_message ? <p className="text-xs text-danger">{item.error_message}</p> : null}
            <Button size="sm" variant="secondary" onClick={onRegenerate} disabled={pending}>
              <RotateCcw className="size-3.5" aria-hidden />
              重新生成这张
            </Button>
          </>
        ) : null}
      </figcaption>
    </figure>
  );
}

/** 图片资产画布：以母图为基准的批量插画；失败项可单张重出（部分成功不清空整批）。 */
export function ImageAssetsCanvas({ workspace, onItemAction, itemActionPending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(imageAssetsContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="图片资产" />;
  const failedCount = content.items.filter((item) => item.status === "failed").length;
  return (
    <div className="space-y-3">
      {failedCount > 0 ? (
        <p className="text-sm text-warning">
          有 {failedCount} 张图片生成失败，其余图片已保留；可对失败项单独重出，不影响已完成的图片。
        </p>
      ) : null}
      <div className="grid gap-3 xl:grid-cols-4 lg:grid-cols-3 md:grid-cols-2">
        {content.items.map((item) => (
          <ImageAssetCard
            key={item.image_id}
            item={item}
            pending={itemActionPending}
            onRegenerate={() => onItemAction({ itemId: item.image_id, action: "regenerate" })}
          />
        ))}
      </div>
    </div>
  );
}

function FineShotRow({
  shot,
  pending,
  onReplaceFrame,
}: {
  shot: { shot_id: string; shot_no: number; scene_title: string; description: string; first_frame_asset_id: string | null; motion_notes: string; camera: string; subtitle_text: string; duration_seconds: number };
  pending?: boolean;
  onReplaceFrame: () => void;
}) {
  const frame = useAssetDetail(shot.first_frame_asset_id);
  return (
    <li className="flex gap-3 rounded-card border border-line bg-surface-1 p-3">
      <div className="w-40 shrink-0">
        {frame.data?.asset.thumbnail_url ? (
          <img src={frame.data.asset.thumbnail_url} alt={`镜头${shot.shot_no}首帧`} className="aspect-video w-full rounded-control object-cover" />
        ) : (
          <span className="flex aspect-video items-center justify-center rounded-control bg-surface-2 text-ink-muted">
            <ImageIcon className="size-5" aria-hidden />
          </span>
        )}
        <Button size="sm" variant="ghost" className="mt-1.5 w-full" onClick={onReplaceFrame} disabled={pending}>
          <Replace className="size-3.5" aria-hidden />
          替换首帧
        </Button>
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink-1">#{shot.shot_no}</span>
          <span className="text-xs text-ink-muted">
            {shot.scene_title} · {shot.duration_seconds}s · {shot.camera}
          </span>
        </div>
        <p className="mt-1 text-sm leading-6 text-ink-2">{shot.description}</p>
        {shot.motion_notes ? <p className="mt-0.5 text-xs leading-5 text-ink-muted">运动：{shot.motion_notes}</p> : null}
        {shot.subtitle_text ? <p className="mt-0.5 text-xs leading-5 text-ink-muted">字幕：{shot.subtitle_text}</p> : null}
      </div>
    </li>
  );
}

/** 细分镜画布：首帧图 + 运动说明 + 字幕；支持从资产库替换首帧（图片一键入视频链）。 */
export function FineStoryboardCanvas({ workspace, projectId, onItemAction, itemActionPending }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(fineStoryboardContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const [pickerFor, setPickerFor] = useState<string | null>(null);
  if (!content) return <InvalidContent nodeTitle="细分镜" />;
  return (
    <div>
      <ul className="space-y-3">
        {content.shots.map((shot) => (
          <FineShotRow
            key={shot.shot_id}
            shot={shot}
            pending={itemActionPending}
            onReplaceFrame={() => setPickerFor(shot.shot_id)}
          />
        ))}
      </ul>
      <AssetPicker
        open={pickerFor !== null}
        onOpenChange={(open) => {
          if (!open) setPickerFor(null);
        }}
        projectId={projectId}
        defaultType="image"
        title="选择首帧图片"
        confirmLabel="设为该镜头首帧"
        onConfirm={(asset) => {
          if (pickerFor) {
            onItemAction({ itemId: pickerFor, action: "replace_image", payload: { asset_id: asset.asset_id } });
          }
        }}
      />
    </div>
  );
}

/** 镜头提示词画布：每个镜头的最终生成提示词（可见，不隐藏）。 */
export function ShotPromptsCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(shotPromptsContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="镜头提示词" />;
  return (
    <ul className="space-y-3">
      {content.prompts.map((prompt) => (
        <li key={prompt.shot_id} className="rounded-card border border-line bg-surface-1 p-4">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold text-ink-1">镜头 #{prompt.shot_no}</span>
            {prompt.model_hint ? <span className="text-xs text-ink-muted">{prompt.model_hint}</span> : null}
          </div>
          <pre className="mt-2 whitespace-pre-wrap rounded-control bg-surface-2 px-3 py-2 font-mono text-xs leading-5 text-ink-2">
            {prompt.prompt_text}
          </pre>
          {prompt.negative_prompt ? (
            <p className="mt-1.5 text-xs leading-5 text-ink-muted">负向：{prompt.negative_prompt}</p>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
