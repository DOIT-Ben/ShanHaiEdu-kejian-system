import { useState } from "react";
import { History, ListChecks, PanelRightClose, PanelRightOpen, WandSparkles } from "lucide-react";
import { useArtifactVersion, useNodeRunDetail } from "@/features/node-runs";
import { PromptSection } from "@/features/prompt-editing";
import { VersionHistoryList } from "@/features/version-history";
import { cn } from "@/shared/lib/cn";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui";

/**
 * 右侧上下文抽屉（05 ContextDrawer）：默认收起，不与主画布抢空间。
 * 生成要求（提示词）／检查结果／历史记录。
 */
export function ContextDrawer({ nodeRunId }: { nodeRunId: string | null }) {
  const [open, setOpen] = useState(false);
  const { data: detail } = useNodeRunDetail(open ? nodeRunId : null);
  const versionId = detail?.node_run.current_artifact_version_id ?? null;
  const { data: artifact } = useArtifactVersion(open ? versionId : null);
  const issues = artifact?.version.validation_issues ?? [];

  return (
    <aside
      className={cn(
        "flex shrink-0 flex-col border-l border-line-subtle bg-surface transition-[width] duration-200",
        open ? "w-[var(--sh-advanced-drawer-width)]" : "w-12",
      )}
      aria-label="参考与检查"
    >
      <div className={cn("flex items-center border-b border-line-subtle py-2", open ? "justify-between px-3" : "justify-center px-1")}>
        {open ? <span className="text-xs font-medium text-ink-muted">参考与检查</span> : null}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "收起右侧栏" : "展开右侧栏"}
          className="flex size-7 items-center justify-center rounded-md text-ink-muted transition-colors duration-150 hover:bg-surface-soft hover:text-ink-strong"
        >
          {open ? <PanelRightClose className="size-4" aria-hidden /> : <PanelRightOpen className="size-4" aria-hidden />}
        </button>
      </div>
      {open ? (
        nodeRunId ? (
          <Tabs defaultValue="prompt" className="flex min-h-0 flex-1 flex-col">
            <TabsList className="mx-3 mt-3">
              <TabsTrigger value="prompt">
                <WandSparkles className="size-3.5" aria-hidden />
                生成要求
              </TabsTrigger>
              <TabsTrigger value="checks">
                <ListChecks className="size-3.5" aria-hidden />
                检查结果{issues.length > 0 ? `（${issues.length}）` : ""}
              </TabsTrigger>
              <TabsTrigger value="history">
                <History className="size-3.5" aria-hidden />
                历史记录
              </TabsTrigger>
            </TabsList>
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <TabsContent value="prompt">
                <PromptSection nodeRunId={nodeRunId} defaultOpen />
              </TabsContent>
              <TabsContent value="checks">
                {issues.length === 0 ? (
                  <p className="rounded-md border border-dashed border-line bg-surface-soft p-4 text-sm text-ink-muted">
                    当前版本没有需要注意的检查结果。
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {issues.map((issue) => (
                      <li
                        key={issue.key}
                        className={cn(
                          "rounded-md border p-3 text-sm",
                          issue.severity === "error"
                            ? "border-danger-200 bg-danger-50 text-danger-700"
                            : issue.severity === "warning"
                              ? "border-warning-200 bg-warning-50 text-warning-700"
                              : "border-line-subtle bg-surface-soft text-ink",
                        )}
                      >
                        {issue.message}
                      </li>
                    ))}
                  </ul>
                )}
              </TabsContent>
              <TabsContent value="history">
                <VersionHistoryList
                  versions={detail?.versions ?? []}
                  currentVersionId={detail?.node_run.current_artifact_version_id ?? null}
                />
              </TabsContent>
            </div>
          </Tabs>
        ) : (
          <p className="p-4 text-sm text-ink-muted">当前步骤没有可展示的参考内容。</p>
        )
      ) : null}
    </aside>
  );
}
