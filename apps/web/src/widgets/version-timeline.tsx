import type { ArtifactVersion } from "@/shared/api/types";
import { formatRelativeTime } from "@/shared/lib/format";
import { cn } from "@/shared/lib/cn";
import { ArtifactStatusBadge, EmptyState } from "@/shared/ui";
import type { ArtifactStatus } from "@/shared/lib/status";

const SOURCE_LABEL: Record<string, string> = {
  generated: "系统生成",
  edited: "教师编辑",
  revision: "修订生成",
  corrected: "校正提交",
  imported: "导入",
};

/** 版本时间线（检查器「版本」页签）：查看/对比/回看历史版本。 */
export function VersionTimeline({
  versions,
  selectedVersionId,
  onSelect,
}: {
  versions: ArtifactVersion[];
  selectedVersionId?: string | null;
  onSelect?: (version: ArtifactVersion) => void;
}) {
  if (versions.length === 0) {
    return <EmptyState title="暂无版本" description="生成或保存后，版本记录会显示在这里。" className="py-8" />;
  }
  return (
    <ol className="space-y-1.5">
      {versions.map((version) => {
        const selected = version.artifact_version_id === selectedVersionId;
        return (
          <li key={version.artifact_version_id}>
            <button
              type="button"
              onClick={() => onSelect?.(version)}
              className={cn(
                "w-full rounded-control border px-3 py-2.5 text-left transition-colors",
                selected ? "border-brand bg-brand-selected" : "border-line bg-surface-1 hover:bg-surface-hover",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-ink-1">第 {version.version_number} 版</span>
                <ArtifactStatusBadge status={version.status as ArtifactStatus} />
              </div>
              <p className="mt-1 text-xs text-ink-muted">
                {SOURCE_LABEL[version.source ?? "generated"] ?? version.source}
                {" · "}
                {formatRelativeTime(version.created_at)}
              </p>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
