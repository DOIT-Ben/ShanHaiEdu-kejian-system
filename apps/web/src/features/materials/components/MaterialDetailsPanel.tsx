import { AlertTriangle, FileCheck2, RefreshCw } from "lucide-react";
import type { FileAssetDto, MaterialParseVersionDto } from "@/features/materials/api/materialsApi";
import { Button } from "@/shared/ui/Button";
import { StatusBadge } from "@/shared/ui/StatusBadge";

type MaterialDetailsPanelProps = {
  asset?: FileAssetDto;
  errorMessage?: string;
  loading?: boolean;
  onRefresh: () => void;
  parseVersions: readonly MaterialParseVersionDto[];
};

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function parseStatus(status: MaterialParseVersionDto["status"]) {
  if (status === "succeeded") return "approved";
  if (status === "failed") return "failed";
  if (status === "running") return "running";
  return "queued";
}

function assetStatus(status: FileAssetDto["status"]) {
  if (status === "active") return "approved";
  if (status === "rejected") return "failed";
  return "running";
}

function scanStatus(status: FileAssetDto["current_version"]["scan_status"]) {
  if (status === "clean") return "已通过";
  if (status === "rejected") return "未通过";
  return "检查中";
}

export function MaterialDetailsPanel({
  asset,
  errorMessage,
  loading = false,
  onRefresh,
  parseVersions,
}: MaterialDetailsPanelProps) {
  const firstLoad = loading && !asset && parseVersions.length === 0;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-[var(--sh-ink-strong)]">教材文件</h2>
          <p className="mt-1 text-sm text-[var(--sh-ink-muted)]">显示文件校验和服务端解析记录。</p>
        </div>
        <Button disabled={loading} onClick={onRefresh} size="sm" variant="secondary">
          <RefreshCw aria-hidden="true" className={loading ? "animate-spin" : ""} />
          刷新教材状态
        </Button>
      </div>

      {errorMessage ? (
        <p
          className="rounded-[var(--sh-radius-sm)] bg-[var(--sh-danger-soft)] p-3 text-sm text-[var(--sh-danger)]"
          role="alert"
        >
          {errorMessage}
        </p>
      ) : null}

      {firstLoad ? (
        <div
          className="space-y-4 rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5"
          role="status"
        >
          <span className="block h-5 w-32 animate-pulse rounded bg-[var(--sh-surface-soft)] motion-reduce:animate-none" />
          <div className="grid gap-3 sm:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <span
                className="block h-14 animate-pulse rounded-[var(--sh-radius-sm)] bg-[var(--sh-surface-soft)] motion-reduce:animate-none"
                key={item}
              />
            ))}
          </div>
          <span className="sr-only">正在读取教材文件和解析记录</span>
        </div>
      ) : asset ? (
        <section className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5">
          <div className="flex items-start gap-3">
            <FileCheck2 aria-hidden="true" className="mt-0.5 size-5 text-[var(--sh-success)]" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="truncate font-semibold text-[var(--sh-ink-strong)]">教材 PDF</h3>
                <StatusBadge status={assetStatus(asset.status)} />
              </div>
              <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-[var(--sh-ink-faint)]">文件大小</dt>
                  <dd className="mt-1 text-[var(--sh-ink-default)]">
                    {formatBytes(asset.current_version.byte_size)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[var(--sh-ink-faint)]">页数</dt>
                  <dd className="mt-1 text-[var(--sh-ink-default)]">
                    {asset.current_version.page_count === null
                      ? "未提供"
                      : `${String(asset.current_version.page_count)} 页`}
                  </dd>
                </div>
                <div>
                  <dt className="text-[var(--sh-ink-faint)]">安全扫描</dt>
                  <dd className="mt-1 text-[var(--sh-ink-default)]">
                    {scanStatus(asset.current_version.scan_status)}
                  </dd>
                </div>
              </dl>
              <p className="mt-4 break-all font-mono text-xs text-[var(--sh-ink-faint)]">
                SHA-256 {asset.current_version.sha256}
              </p>
            </div>
          </div>
        </section>
      ) : (
        <p className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-6 text-sm text-[var(--sh-ink-muted)]">
          尚未读取到教材文件。
        </p>
      )}

      {!firstLoad ? (
        <section aria-labelledby="material-parse-title">
          <h2
            className="text-lg font-semibold text-[var(--sh-ink-strong)]"
            id="material-parse-title"
          >
            解析记录
          </h2>
          <div className="mt-3 grid gap-3">
            {parseVersions.length ? (
              parseVersions.map((version) => (
                <article
                  className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4"
                  key={version.id}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="font-semibold text-[var(--sh-ink-strong)]">
                      第 {version.version_no} 次解析
                    </h3>
                    <StatusBadge status={parseStatus(version.status)} />
                  </div>
                  <p className="mt-2 text-sm text-[var(--sh-ink-muted)]">
                    {version.page_count === null
                      ? "页数尚未确认"
                      : `${String(version.page_count)} 页`}
                  </p>
                  {version.error_code ? (
                    <p
                      className="mt-3 flex items-center gap-2 text-sm text-[var(--sh-danger)]"
                      role="alert"
                    >
                      <AlertTriangle aria-hidden="true" className="size-4" />
                      本次解析没有完成，请稍后重试或重新上传教材。
                    </p>
                  ) : null}
                </article>
              ))
            ) : (
              <p className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-5 text-sm text-[var(--sh-ink-muted)]">
                暂无解析记录。
              </p>
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
}
