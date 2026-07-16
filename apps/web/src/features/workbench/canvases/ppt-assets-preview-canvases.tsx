import { useMemo } from "react";
import { z } from "zod";
import { ImageIcon, RotateCcw } from "lucide-react";
import { parseContent, pptPagesContentSchema, pptLayoutLabels } from "@/entities/content";
import { useArtifactVersion } from "@/features/artifacts";
import { useAssetDetail } from "@/features/assets";
import { cn } from "@/shared/lib/cn";
import { Badge, Button, EmptyState, Skeleton } from "@/shared/ui";
import type { CanvasProps } from "../registry";
import { InvalidContent } from "./invalid-content";

const pptAssetsContentSchema = z.object({
  generated_asset_ids: z.array(z.string()).default([]),
});

function AssetTile({ assetId, onRegenerate, pending }: { assetId: string; onRegenerate?: () => void; pending?: boolean }) {
  const asset = useAssetDetail(assetId);
  if (asset.isPending) return <Skeleton className="h-40" />;
  const data = asset.data?.asset;
  return (
    <figure className="overflow-hidden rounded-card border border-line bg-surface-1">
      {data?.thumbnail_url ? (
        <img src={data.thumbnail_url} alt={data.name} className="h-32 w-full object-cover" />
      ) : (
        <span className="flex h-32 items-center justify-center bg-surface-2 text-ink-muted">
          <ImageIcon className="size-6" aria-hidden />
        </span>
      )}
      <figcaption className="flex items-center justify-between gap-2 px-3 py-2">
        <span className="truncate text-xs text-ink-1">{data?.name ?? assetId}</span>
        {onRegenerate ? (
          <Button size="sm" variant="ghost" onClick={onRegenerate} disabled={pending} title="重新生成这张插图">
            <RotateCcw className="size-3.5" aria-hidden />
          </Button>
        ) : null}
      </figcaption>
    </figure>
  );
}

/** PPT 配图画布：本步骤生成的教学插图。 */
export function PptAssetsCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(pptAssetsContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  if (!content) return <InvalidContent nodeTitle="PPT配图" />;
  if (content.generated_asset_ids.length === 0) {
    return <EmptyState title="本次未生成插图" description="页面脚本中没有需要配图的页面。" />;
  }
  return (
    <div className="grid gap-3 lg:grid-cols-3 md:grid-cols-2">
      {content.generated_asset_ids.map((assetId) => (
        <AssetTile key={assetId} assetId={assetId} />
      ))}
    </div>
  );
}

const previewContentSchema = z.object({
  key_sample_page_ids: z.array(z.string()).default([]),
  note: z.string().default(""),
});

/** 整册预览画布：读取上游页面产物，突出关键样张。 */
export function PptPreviewCanvas({ workspace }: CanvasProps) {
  const latest = workspace.artifact_versions[0];
  const content = useMemo(
    () => parseContent(previewContentSchema, latest?.content),
    [latest?.artifact_version_id, latest?.content],
  );
  const pagesRef = workspace.upstream_references?.find((ref) => ref.node_key === "ppt_pages");
  const pagesArtifact = useArtifactVersion(pagesRef?.artifact_version_id ?? null);
  const pagesContent = useMemo(
    () => parseContent(pptPagesContentSchema, pagesArtifact.data?.content),
    [pagesArtifact.data],
  );

  if (!content) return <InvalidContent nodeTitle="整册预览" />;
  if (pagesArtifact.isPending) {
    return (
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="aspect-video" />
        ))}
      </div>
    );
  }
  if (!pagesContent) {
    return <EmptyState title="缺少页面内容" description="请先完成「页面脚本」步骤，再进行整册预览。" />;
  }

  const keySet = new Set(content.key_sample_page_ids);
  return (
    <div className="space-y-4">
      {content.note ? <p className="rounded-control bg-brand-selected px-3 py-2 text-sm text-brand">{content.note}</p> : null}
      <div className="grid gap-3 xl:grid-cols-4 lg:grid-cols-3 md:grid-cols-2">
        {pagesContent.pages.map((page) => {
          const isKey = keySet.has(page.page_id);
          const isCover = page.layout === "cover";
          return (
            <figure
              key={page.page_id}
              className={cn(
                "overflow-hidden rounded-card border",
                isKey ? "border-brand ring-2 ring-brand/25" : "border-line",
              )}
            >
              <div
                className={cn("aspect-video p-3", isCover ? "text-white" : "bg-white")}
                style={isCover ? { background: `linear-gradient(135deg, ${pagesContent.theme.accent_color}, #10225E)` } : undefined}
              >
                <p className={cn("text-[9px]", isCover ? "text-white/70" : "text-ink-muted")}>第 {page.page_no} 页</p>
                <p className={cn("mt-0.5 truncate font-semibold", isCover ? "text-sm text-white" : "text-xs")} style={isCover ? undefined : { color: "#182033" }}>
                  {page.title}
                </p>
              </div>
              <figcaption className="flex items-center justify-between px-2.5 py-1.5">
                <span className="text-[10px] text-ink-muted">{pptLayoutLabels[page.layout]}</span>
                {isKey ? <Badge tone="brand">关键样张</Badge> : null}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </div>
  );
}
