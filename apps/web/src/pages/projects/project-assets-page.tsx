import { useMemo, useState } from "react";
import { useOutletContext } from "react-router";
import { Download, ImageIcon, Search } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { useAssetDetail, useDownloadFile, useProjectAssets, type AssetFilters } from "@/features/assets";
import { useDebouncedCallback } from "@/shared/hooks";
import { getNodeDef, LESSON_NODES } from "@/entities/workflow/nodes";
import { formatFileSize, formatRelativeTime } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import type { AssetStatus } from "@/shared/lib/status";
import {
  AssetStatusBadge,
  Button,
  Drawer,
  DrawerContent,
  EmptyState,
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Spinner,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

const TYPE_OPTIONS = [
  { value: "all", label: "全部类型" },
  { value: "image", label: "图片" },
  { value: "video", label: "视频" },
  { value: "audio", label: "音频" },
  { value: "subtitle", label: "字幕" },
  { value: "document", label: "文档" },
];

function AssetDetailDrawer({ assetId, onClose }: { assetId: string | null; onClose: () => void }) {
  const detail = useAssetDetail(assetId);
  const download = useDownloadFile();
  const asset = detail.data?.asset;
  const versions = detail.data?.versions ?? [];
  const references = detail.data?.usage_references ?? [];
  return (
    <Drawer open={assetId !== null} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent title={asset?.name ?? "资产详情"}>
        {detail.isPending ? (
          <div className="space-y-3">
            <Skeleton className="aspect-video" />
            <Skeleton className="h-24" />
          </div>
        ) : detail.isError ? (
          <AppErrorPanel error={detail.error} title="资产详情加载失败" onRetry={() => void detail.refetch()} />
        ) : asset ? (
          <div className="space-y-4">
            {asset.thumbnail_url ? (
              <img src={asset.thumbnail_url} alt={asset.name} className="w-full rounded-card border border-line object-cover" />
            ) : (
              <span className="flex aspect-video items-center justify-center rounded-card bg-surface-2 text-ink-muted">
                <ImageIcon className="size-8" aria-hidden />
              </span>
            )}
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">状态</dt>
                <dd>
                  <AssetStatusBadge status={asset.status as AssetStatus} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">来源步骤</dt>
                <dd className="text-ink-1">{asset.source_node_key ? (getNodeDef(asset.source_node_key)?.title ?? asset.source_node_key) : "—"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-ink-muted">创建时间</dt>
                <dd className="text-ink-1">{formatRelativeTime(asset.created_at)}</dd>
              </div>
            </dl>
            <section>
              <h4 className="mb-1.5 text-xs font-semibold text-ink-muted">版本（{versions.length}）</h4>
              <ul className="space-y-1.5">
                {versions.map((version) => (
                  <li key={version.asset_version_id} className="flex items-center justify-between gap-2 rounded-control border border-line px-3 py-2">
                    <span className="text-sm text-ink-1">V{version.version_number}</span>
                    <span className="text-xs text-ink-muted">
                      {version.file_object ? formatFileSize(version.file_object.size_bytes) : ""}
                    </span>
                    {version.file_object ? (
                      <Button
                        size="sm"
                        variant="ghost"
                        loading={download.isPending}
                        onClick={() =>
                          download.mutate({ fileObjectId: version.file_object!.file_object_id, fileName: version.file_object!.file_name })
                        }
                      >
                        <Download className="size-3.5" aria-hidden />
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
            <section>
              <h4 className="mb-1.5 text-xs font-semibold text-ink-muted">被引用（{references.length}）</h4>
              {references.length === 0 ? (
                <p className="text-xs text-ink-muted">尚未被下游步骤引用。</p>
              ) : (
                <ul className="space-y-1 text-sm text-ink-2">
                  {references.map((reference, index) => (
                    <li key={index}>
                      {reference.lesson_title ? `${reference.lesson_title} · ` : ""}
                      {reference.node_title}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        ) : null}
      </DrawerContent>
    </Drawer>
  );
}

/** 资产库页：类型/来源/关键字过滤 + 无限滚动网格 + 详情抽屉。 */
export function ProjectAssetsPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const [filters, setFilters] = useState<AssetFilters>({});
  const [keywordInput, setKeywordInput] = useState("");
  const [activeAssetId, setActiveAssetId] = useState<string | null>(null);
  const assets = useProjectAssets(project.project_id, filters);
  const debouncedKeyword = useDebouncedCallback((keyword: string) => {
    setFilters((prev) => ({ ...prev, keyword: keyword || undefined }));
  }, 300);

  const items = useMemo(() => (assets.data?.pages ?? []).flatMap((page) => page.assets), [assets.data]);

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="资产" description="项目内所有生成与上传的素材；图片可在细分镜中一键设为镜头首帧。" />
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <Input
            className="pl-8"
            placeholder="搜索资产名称"
            value={keywordInput}
            onChange={(event) => {
              setKeywordInput(event.target.value);
              debouncedKeyword.run(event.target.value);
            }}
          />
        </div>
        <Select
          value={filters.type ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, type: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-32" aria-label="按类型筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TYPE_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filters.source_node_key ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, source_node_key: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-40" aria-label="按来源步骤筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部来源</SelectItem>
            {LESSON_NODES.filter((node) => ["image_gen", "video_gen", "tts", "pptx_render"].includes(node.capability ?? "")).map((node) => (
              <SelectItem key={node.key} value={node.key}>
                {node.title}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {assets.isPending ? (
        <div className="grid gap-3 xl:grid-cols-5 lg:grid-cols-4 md:grid-cols-3 grid-cols-2">
          {Array.from({ length: 10 }).map((_, index) => (
            <Skeleton key={index} className="h-40" />
          ))}
        </div>
      ) : assets.isError ? (
        <AppErrorPanel error={assets.error} title="资产加载失败" onRetry={() => void assets.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="暂无资产" description="生成步骤产出的图片、视频、音频会汇总在这里。" />
      ) : (
        <>
          <ul className="grid gap-3 xl:grid-cols-5 lg:grid-cols-4 md:grid-cols-3 grid-cols-2">
            {items.map((asset) => (
              <li key={asset.asset_id}>
                <button
                  type="button"
                  onClick={() => setActiveAssetId(asset.asset_id)}
                  className={cn(
                    "w-full overflow-hidden rounded-card border border-line bg-surface-1 text-left transition-shadow hover:shadow-sm",
                  )}
                >
                  {asset.thumbnail_url ? (
                    <img src={asset.thumbnail_url} alt={asset.name} loading="lazy" className="aspect-video w-full object-cover" />
                  ) : (
                    <span className="flex aspect-video items-center justify-center bg-surface-2 text-ink-muted">
                      <ImageIcon className="size-6" aria-hidden />
                    </span>
                  )}
                  <span className="block space-y-1 px-3 py-2">
                    <span className="block truncate text-xs font-medium text-ink-1">{asset.name}</span>
                    <span className="flex items-center justify-between">
                      <AssetStatusBadge status={asset.status as AssetStatus} />
                      <span className="text-[10px] text-ink-muted">{formatRelativeTime(asset.created_at)}</span>
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {assets.hasNextPage ? (
            <div className="text-center">
              <Button variant="secondary" onClick={() => void assets.fetchNextPage()} disabled={assets.isFetchingNextPage}>
                {assets.isFetchingNextPage ? <Spinner label="加载中" /> : "加载更多"}
              </Button>
            </div>
          ) : null}
        </>
      )}

      <AssetDetailDrawer assetId={activeAssetId} onClose={() => setActiveAssetId(null)} />
    </div>
  );
}
