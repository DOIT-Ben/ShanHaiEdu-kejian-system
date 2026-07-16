import { useEffect, useState } from "react";
import { Eye, RotateCcw, ScrollText } from "lucide-react";
import type { PromptVersion } from "@/shared/api/types";
import { formatRelativeTime } from "@/shared/lib/format";
import { Badge, Button, Textarea } from "@/shared/ui";

const PROMPT_SOURCE_LABEL: Record<string, string> = {
  system: "系统组装",
  edited: "教师编辑",
  revision: "修订指令",
};

/**
 * 提示词工作台（检查器「提示词」页签）。
 * 规则：系统组装的最终提示词必须可见、可编辑；
 * 运行时契约只读展示；支持恢复默认。
 */
export function PromptEditor({
  versions,
  saving,
  onSaveEdited,
  onResetDefault,
}: {
  versions: PromptVersion[];
  saving?: boolean;
  onSaveEdited: (editedPrompt: string, baseVersionId: string | null) => void;
  onResetDefault: () => void;
}) {
  const latest = versions[0] ?? null;
  const [draft, setDraft] = useState(latest?.editable_prompt ?? "");
  const [contractOpen, setContractOpen] = useState(false);

  useEffect(() => {
    setDraft(latest?.editable_prompt ?? "");
  }, [latest?.prompt_version_id, latest?.editable_prompt]);

  if (!latest) {
    return (
      <p className="rounded-control bg-surface-2 px-3 py-4 text-sm text-ink-2">
        修改左侧输入后，系统会组装本步骤的完整提示词并显示在这里。
      </p>
    );
  }

  const dirty = draft !== latest.editable_prompt;

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Badge tone={latest.source === "edited" ? "warning" : latest.source === "revision" ? "brand" : "neutral"}>
            {PROMPT_SOURCE_LABEL[latest.source ?? "system"]}
          </Badge>
          <span className="text-xs text-ink-muted">
            第 {latest.version_number} 版 · {formatRelativeTime(latest.created_at)}
          </span>
        </div>
        <Button size="sm" variant="ghost" onClick={onResetDefault} disabled={saving}>
          <RotateCcw className="size-3.5" aria-hidden />
          恢复默认
        </Button>
      </div>

      <div className="min-h-0 flex-1">
        <Textarea
          aria-label="最终提示词（可编辑）"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          className="h-full min-h-56 resize-none font-mono text-xs leading-5"
          spellCheck={false}
        />
      </div>
      {dirty ? (
        <div className="flex items-center justify-between rounded-control bg-brand-selected px-3 py-2">
          <p className="text-xs text-brand">提示词已修改，保存后按新提示词生成。</p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" onClick={() => setDraft(latest.editable_prompt)}>
              放弃修改
            </Button>
            <Button size="sm" loading={saving} onClick={() => onSaveEdited(draft, latest.prompt_version_id)}>
              保存为新版本
            </Button>
          </div>
        </div>
      ) : null}

      <div className="rounded-control border border-line bg-surface-2">
        <button
          type="button"
          className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-ink-2"
          onClick={() => setContractOpen((open) => !open)}
          aria-expanded={contractOpen}
        >
          <ScrollText className="size-3.5" aria-hidden />
          运行时契约（系统追加，只读）
          <Eye className="ml-auto size-3.5 text-ink-muted" aria-hidden />
        </button>
        {contractOpen ? (
          <pre className="max-h-40 overflow-auto whitespace-pre-wrap border-t border-line px-3 py-2 font-mono text-xs leading-5 text-ink-2">
            {latest.runtime_contract}
          </pre>
        ) : null}
      </div>

      {versions.length > 1 ? (
        <details className="text-xs text-ink-muted">
          <summary className="cursor-pointer select-none">提示词历史（{versions.length} 个版本）</summary>
          <ul className="mt-2 space-y-1">
            {versions.slice(1).map((version) => (
              <li key={version.prompt_version_id} className="flex items-center justify-between gap-2">
                <span>
                  第 {version.version_number} 版 · {PROMPT_SOURCE_LABEL[version.source ?? "system"]} ·{" "}
                  {formatRelativeTime(version.created_at)}
                </span>
                <button
                  type="button"
                  className="font-medium text-brand hover:underline"
                  onClick={() => setDraft(version.editable_prompt)}
                >
                  载入
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
