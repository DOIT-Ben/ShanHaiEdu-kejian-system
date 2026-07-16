import { CheckCircle2, CircleDashed, Download, FileWarning, Package } from "lucide-react";
import type { Delivery, DeliveryItem } from "@/shared/api/types";
import { useDownloadFile } from "@/features/assets";
import { formatFileSize } from "@/shared/lib/format";
import { Badge, Button } from "@/shared/ui";

const STATUS_META: Record<DeliveryItem["status"], { label: string; tone: "neutral" | "brand" | "success" | "warning" | "danger" }> = {
  missing: { label: "缺失", tone: "danger" },
  pending: { label: "待完成", tone: "neutral" },
  blocked: { label: "被阻塞", tone: "warning" },
  ready: { label: "已就绪", tone: "brand" },
  delivered: { label: "已交付", tone: "success" },
};

const CATEGORY_LABEL: Record<DeliveryItem["category"], string> = {
  lesson_plan: "教案",
  ppt: "PPT",
  video: "视频",
  subtitle: "字幕",
  audio: "音频",
  quality_report: "质量报告",
  package: "交付包",
};

/** 交付清单：逐项状态 + 可下载项 + 阻塞原因。 */
export function DeliveryChecklist({ delivery }: { delivery: Delivery }) {
  const download = useDownloadFile();
  return (
    <div className="space-y-3">
      <ul className="divide-y divide-divider rounded-panel border border-line bg-surface-1">
        {delivery.items.map((item) => {
          const meta = STATUS_META[item.status];
          return (
            <li key={item.item_key} className="flex items-center gap-3 px-4 py-3">
              {item.status === "delivered" || item.status === "ready" ? (
                <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
              ) : (
                <CircleDashed className="size-4 shrink-0 text-ink-muted" aria-hidden />
              )}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-ink-1">{item.title}</p>
                <p className="text-xs text-ink-muted">
                  {CATEGORY_LABEL[item.category]}
                  {item.version_number ? ` · 第 ${item.version_number} 版` : ""}
                  {item.file_object ? ` · ${formatFileSize(item.file_object.size_bytes)}` : ""}
                </p>
              </div>
              <Badge tone={meta.tone}>{meta.label}</Badge>
              {item.file_object ? (
                <Button
                  size="sm"
                  variant="ghost"
                  loading={download.isPending}
                  onClick={() =>
                    download.mutate({ fileObjectId: item.file_object!.file_object_id, fileName: item.file_object!.file_name })
                  }
                >
                  <Download className="size-3.5" aria-hidden />
                  下载
                </Button>
              ) : null}
            </li>
          );
        })}
      </ul>
      {delivery.blockers.length > 0 ? (
        <div className="rounded-panel border border-warning/40 bg-warning-surface px-4 py-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-ink-1">
            <FileWarning className="size-4 text-warning" aria-hidden />
            以下事项完成后才能打包交付
          </p>
          <ul className="mt-1.5 list-inside list-disc space-y-0.5 text-xs text-ink-2">
            {delivery.blockers.map((blocker, index) => (
              <li key={index}>{blocker.message}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {delivery.package_file ? (
        <div className="flex items-center gap-3 rounded-panel border border-success/40 bg-success-surface px-4 py-3">
          <Package className="size-5 text-success" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-ink-1">{delivery.package_file.file_name}</p>
            <p className="text-xs text-ink-2">{formatFileSize(delivery.package_file.size_bytes)} · 打包完成</p>
          </div>
          <Button
            size="sm"
            loading={download.isPending}
            onClick={() =>
              download.mutate({ fileObjectId: delivery.package_file!.file_object_id, fileName: delivery.package_file!.file_name })
            }
          >
            <Download className="size-4" aria-hidden />
            下载交付包
          </Button>
        </div>
      ) : null}
    </div>
  );
}
