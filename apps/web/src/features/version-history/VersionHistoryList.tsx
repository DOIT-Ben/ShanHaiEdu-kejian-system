import { History } from "lucide-react";
import { formatDateTime } from "@/shared/lib/format";
import { getArtifactStatusMeta } from "@/shared/lib/status";
import { Badge } from "@/shared/ui";

interface VersionEntry {
  id: string;
  version_no: number;
  review_status: string;
  source?: string;
  created_at: string;
}

const SOURCE_LABELS: Record<string, string> = {
  generated: "系统生成",
  teacher_edited: "老师修改",
  imported: "导入",
};

/** 历史记录（右侧抽屉）：版本只读回看；当前版本高亮。 */
export function VersionHistoryList({
  versions,
  currentVersionId,
}: {
  versions: VersionEntry[];
  currentVersionId: string | null;
}) {
  if (versions.length === 0) {
    return (
      <p className="flex items-center gap-2 rounded-md border border-dashed border-line bg-surface-soft p-4 text-sm text-ink-muted">
        <History className="size-4" aria-hidden />
        还没有历史版本。
      </p>
    );
  }
  return (
    <ol className="space-y-2">
      {versions.map((version) => {
        const meta = getArtifactStatusMeta(version.review_status);
        const isCurrent = version.id === currentVersionId;
        return (
          <li
            key={version.id}
            className={`rounded-md border p-3 ${
              isCurrent ? "border-brand-300 bg-brand-50/50" : "border-line-subtle bg-surface"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-ink-strong">
                第 {version.version_no} 版
                {isCurrent ? <span className="ml-1.5 text-xs font-normal text-brand-600">当前</span> : null}
              </span>
              <Badge tone={meta.tone}>{meta.label}</Badge>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {(version.source ? SOURCE_LABELS[version.source] : null) ?? version.source ?? "系统生成"} · {formatDateTime(version.created_at)}
            </p>
          </li>
        );
      })}
    </ol>
  );
}
