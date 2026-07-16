import { useState } from "react";
import { ImageIcon, Search } from "lucide-react";
import type { Asset } from "@/shared/api/types";
import { useProjectAssets } from "@/features/assets";
import { formatRelativeTime } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import type { AssetStatus } from "@/shared/lib/status";
import {
  AssetStatusBadge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  EmptyState,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Spinner,
} from "@/shared/ui";

const TYPE_LABEL: Record<string, string> = {
  image: "图片",
  video: "视频",
  audio: "音频",
  subtitle: "字幕",
  document: "文档",
};

/**
 * 资产选择器：跨节点复用资产（如把图片资产一键带入视频节点）。
 * 支持类型/关键字过滤与预览。
 */
export function AssetPicker({
  open,
  onOpenChange,
  projectId,
  defaultType,
  title = "选择资产",
  confirmLabel = "使用所选资产",
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  defaultType?: string;
  title?: string;
  confirmLabel?: string;
  onConfirm: (asset: Asset) => void;
}) {
  const [type, setType] = useState<string>(defaultType ?? "image");
  const [keyword, setKeyword] = useState("");
  const [selected, setSelected] = useState<Asset | null>(null);
  const assets = useProjectAssets(projectId, { type, keyword: keyword || undefined });
  const items = (assets.data?.pages ?? []).flatMap((page) => page.assets);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={title} description="资产来自本项目的各生成步骤，可跨节点复用。" className="max-w-3xl">
        <div className="flex items-center gap-2">
          <Select value={type} onValueChange={setType}>
            <SelectTrigger className="w-28" aria-label="资产类型">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(TYPE_LABEL).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
            <Input
              className="pl-8"
              placeholder="搜索资产名称"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
            />
          </div>
        </div>

        <div className="mt-3 max-h-96 min-h-40 overflow-y-auto">
          {assets.isPending ? (
            <div className="grid grid-cols-3 gap-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <Skeleton key={index} className="h-32" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <EmptyState title="没有符合条件的资产" description="调整类型或关键字，或先在上游步骤生成资产。" />
          ) : (
            <ul className="grid grid-cols-3 gap-3">
              {items.map((asset) => {
                const isSelected = selected?.asset_id === asset.asset_id;
                return (
                  <li key={asset.asset_id}>
                    <button
                      type="button"
                      onClick={() => setSelected(asset)}
                      className={cn(
                        "w-full overflow-hidden rounded-card border text-left transition-colors",
                        isSelected ? "border-brand ring-2 ring-brand/30" : "border-line hover:border-ink-muted",
                      )}
                      aria-pressed={isSelected}
                    >
                      {asset.thumbnail_url ? (
                        <img src={asset.thumbnail_url} alt={asset.name} className="h-24 w-full object-cover" />
                      ) : (
                        <span className="flex h-24 w-full items-center justify-center bg-surface-2 text-ink-muted">
                          <ImageIcon className="size-6" aria-hidden />
                        </span>
                      )}
                      <span className="block space-y-1 px-2.5 py-2">
                        <span className="block truncate text-xs font-medium text-ink-1">{asset.name}</span>
                        <span className="flex items-center justify-between gap-1">
                          <AssetStatusBadge status={asset.status as AssetStatus} />
                          <span className="text-[10px] text-ink-muted">{formatRelativeTime(asset.created_at)}</span>
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {assets.hasNextPage ? (
            <div className="mt-3 text-center">
              <Button variant="ghost" size="sm" onClick={() => void assets.fetchNextPage()} disabled={assets.isFetchingNextPage}>
                {assets.isFetchingNextPage ? <Spinner label="加载中" /> : "加载更多"}
              </Button>
            </div>
          ) : null}
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            disabled={!selected}
            onClick={() => {
              if (selected) {
                onConfirm(selected);
                onOpenChange(false);
              }
            }}
          >
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
