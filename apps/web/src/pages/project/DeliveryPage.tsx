import { useParams } from "react-router";
import { Archive, Download, FileText, Package } from "lucide-react";
import { useCreateDeliveryPackage, useDelivery, useDownloadAssetVersion } from "@/features/assets";
import { formatDateTime, formatFileSize } from "@/shared/lib/format";
import { Badge, Button, PageHeader, Panel, PanelBody, PanelHeader, Skeleton, Spinner, toast } from "@/shared/ui";
import type { StatusTone } from "@/shared/lib/status";

const READINESS_META: Record<string, { label: string; tone: StatusTone }> = {
  approved: { label: "已完成", tone: "success" },
  pending: { label: "待完成", tone: "warning" },
  blocked: { label: "受阻", tone: "danger" },
  disabled: { label: "未启用", tone: "neutral" },
  skipped: { label: "已跳过", tone: "neutral" },
};

const FILE_KIND_LABELS: Record<string, string> = {
  docx: "Word 文档",
  pdf: "PDF",
  pptx: "PPT",
  mp4: "视频",
  srt: "字幕",
  report: "说明报告",
  archive: "打包文件",
};

/** 项目交付（04 §1.6）：完备性检查 → 打包 → 下载。 */
export default function DeliveryPage() {
  const { projectId = "" } = useParams();
  const { data, isPending } = useDelivery(projectId);
  const createPackage = useCreateDeliveryPackage(projectId);
  const download = useDownloadAssetVersion();

  if (isPending || !data) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 px-6 py-8">
        <Skeleton className="h-10 w-1/2" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  const packaging = data.status === "packaging";
  const canPackage = data.status === "ready" || data.status === "stale" || data.status === "packaged";

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <PageHeader
        title="项目交付"
        description="确认各课时作品完成后，一键打包下载全部成果。"
        actions={
          <Button
            disabled={!canPackage || packaging}
            loading={createPackage.isPending || packaging}
            loadingText={packaging ? "正在打包…" : "正在开始…"}
            onClick={() =>
              createPackage.mutate(undefined, {
                onSuccess: () => toast({ tone: "info", title: "开始打包", description: "完成后可直接下载。" }),
                onError: (error) => toast({ tone: "danger", title: "无法打包", description: error.message }),
              })
            }
          >
            <Package className="size-4" aria-hidden />
            {data.package ? "重新打包" : "打包全部成果"}
          </Button>
        }
      />

      {data.status === "stale" ? (
        <p className="mt-5 rounded-lg border border-warning-200 bg-warning-50 p-4 text-sm text-ink">
          打包之后内容有更新，建议重新打包以获取最新版本。
        </p>
      ) : null}

      <div className="mt-6 space-y-6">
        <Panel>
          <PanelHeader title="交付检查" description="每个课时的作品是否就绪。" />
          <PanelBody className="p-0">
            <ul className="divide-y divide-line-subtle">
              {data.readiness.map((item, index) => {
                const meta = READINESS_META[item.state] ?? { label: item.state, tone: "neutral" as StatusTone };
                return (
                  <li key={index} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                    <FileText className="size-4 shrink-0 text-ink-faint" aria-hidden />
                    <span className="min-w-0 flex-1 text-sm text-ink">
                      {item.lesson_title && !item.label.startsWith(item.lesson_title)
                        ? `${item.lesson_title} · `
                        : ""}
                      {item.label}
                    </span>
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    {item.blockers && item.blockers.length > 0 ? (
                      <span className="w-full pl-7 text-xs text-ink-muted">{item.blockers.join("；")}</span>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader
            title="交付包"
            description={
              data.package
                ? `第 ${data.package.version_no ?? 1} 版 · ${formatDateTime(data.package.created_at ?? "")}`
                : "还没有打包。作品就绪后点击右上角「打包全部成果」。"
            }
          />
          <PanelBody className="p-0">
            {packaging ? (
              <div className="flex items-center gap-3 p-5 text-sm text-ink-muted">
                <Spinner className="size-4" />
                正在打包，请稍候…
              </div>
            ) : data.package?.files && data.package.files.length > 0 ? (
              <ul className="divide-y divide-line-subtle">
                {data.package.files.map((file) => (
                  <li key={file.file_key} className="flex items-center gap-3 px-5 py-3.5">
                    <Archive className="size-4 shrink-0 text-brand-500" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink-strong">{file.title}</span>
                      <span className="mt-0.5 block text-xs text-ink-muted">
                        {FILE_KIND_LABELS[file.kind] ?? file.kind} · {formatFileSize(file.size_bytes)}
                      </span>
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!file.asset_version_id}
                      loading={download.isPending}
                      onClick={() =>
                        file.asset_version_id &&
                        download.mutate(file.asset_version_id, {
                          onSuccess: (result) => window.open(result.url, "_blank", "noopener"),
                          onError: (error) => toast({ tone: "danger", title: "下载失败", description: error.message }),
                        })
                      }
                    >
                      <Download className="size-4" aria-hidden />
                      下载
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-5 text-sm text-ink-muted">暂无可下载文件。</p>
            )}
          </PanelBody>
        </Panel>
      </div>
    </div>
  );
}
