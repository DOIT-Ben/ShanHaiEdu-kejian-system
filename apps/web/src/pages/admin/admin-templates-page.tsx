import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { FileUp, Search } from "lucide-react";
import { useImportTemplate, useTemplates } from "@/features/admin";
import { LESSON_NODES } from "@/entities/workflow/nodes";
import { formatRelativeTime } from "@/shared/lib/format";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  EmptyState,
  FormField,
  Input,
  PageHeader,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Skeleton,
  Textarea,
  toast,
} from "@/shared/ui";
import { AppErrorPanel } from "@/widgets";

export const TEMPLATE_STATUS_META: Record<string, { label: string; tone: "neutral" | "brand" | "success" | "warning" }> = {
  draft: { label: "草稿", tone: "neutral" },
  candidate: { label: "候选", tone: "brand" },
  published: { label: "已发布", tone: "success" },
  deprecated: { label: "已废弃", tone: "warning" },
};

function ImportTemplateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const importTemplate = useImportTemplate();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [nodeType, setNodeType] = useState("lesson_plan");
  const [content, setContent] = useState("");
  const [description, setDescription] = useState("");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="导入 Prompt 模板" description="导入后为草稿状态，需干跑校验并发布后才会生效。" className="max-w-xl">
        <div className="space-y-3">
          <FormField label="模板名称" required>
            {({ id }) => <Input id={id} value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：教案生成 v3" />}
          </FormField>
          <FormField label="适用节点" required>
            {({ id }) => (
              <Select value={nodeType} onValueChange={setNodeType}>
                <SelectTrigger id={id}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LESSON_NODES.map((node) => (
                    <SelectItem key={node.key} value={node.key}>
                      {node.title}（{node.key}）
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField label="模板内容" required description="支持 {{variable}} 变量占位。">
            {({ id }) => (
              <Textarea
                id={id}
                rows={8}
                value={content}
                onChange={(event) => setContent(event.target.value)}
                className="font-mono text-xs"
                placeholder="你是一名小学数学教研专家……"
              />
            )}
          </FormField>
          <FormField label="说明">
            {({ id }) => <Input id={id} value={description} onChange={(event) => setDescription(event.target.value)} />}
          </FormField>
          {importTemplate.isError ? <AppErrorPanel error={importTemplate.error} title="导入失败" /> : null}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            loading={importTemplate.isPending}
            disabled={!name.trim() || !content.trim()}
            onClick={() => {
              importTemplate.mutate(
                { name: name.trim(), node_type: nodeType, content, description: description.trim() || undefined },
                {
                  onSuccess: (detail) => {
                    toast({ tone: "success", title: "模板已导入", description: "请先干跑校验，再发布启用。" });
                    onOpenChange(false);
                    void navigate(`/admin/templates/${detail.template.template_id}`);
                  },
                },
              );
            }}
          >
            导入模板
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Prompt 模板列表页。 */
export function AdminTemplatesPage() {
  const [filters, setFilters] = useState<{ status?: string; keyword?: string }>({});
  const [keywordInput, setKeywordInput] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const templates = useTemplates(filters);

  return (
    <div className="space-y-4 p-6">
      <PageHeader
        title="Prompt 模板"
        description="节点提示词模板的导入、编辑、版本管理与发布。"
        actions={
          <Button onClick={() => setImportOpen(true)}>
            <FileUp className="size-4" aria-hidden />
            导入模板
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-muted" aria-hidden />
          <Input
            className="pl-8"
            placeholder="搜索模板名称"
            value={keywordInput}
            onChange={(event) => {
              setKeywordInput(event.target.value);
              setFilters((prev) => ({ ...prev, keyword: event.target.value || undefined }));
            }}
          />
        </div>
        <Select
          value={filters.status ?? "all"}
          onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value === "all" ? undefined : value }))}
        >
          <SelectTrigger className="w-32" aria-label="按状态筛选">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="published">已发布</SelectItem>
            <SelectItem value="candidate">候选</SelectItem>
            <SelectItem value="draft">草稿</SelectItem>
            <SelectItem value="deprecated">已废弃</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {templates.isPending ? (
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-14" />
          ))}
        </div>
      ) : templates.isError ? (
        <AppErrorPanel error={templates.error} title="模板加载失败" onRetry={() => void templates.refetch()} />
      ) : (templates.data ?? []).length === 0 ? (
        <EmptyState title="暂无模板" description="导入第一份 Prompt 模板。" />
      ) : (
        <ul className="divide-y divide-divider rounded-panel border border-line bg-surface-1">
          {(templates.data ?? []).map((template) => {
            const status = TEMPLATE_STATUS_META[template.status] ?? TEMPLATE_STATUS_META.draft;
            return (
              <li key={template.template_id}>
                <Link
                  to={template.template_id}
                  className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-hover"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-1">{template.name}</p>
                    <p className="text-xs text-ink-muted">
                      {LESSON_NODES.find((node) => node.key === template.node_type)?.title ?? template.node_type} · 当前{" "}
                      {template.current_version} · 使用 {template.usage_count ?? 0} 次
                      {template.updated_at ? ` · 更新于 ${formatRelativeTime(template.updated_at)}` : ""}
                    </p>
                  </div>
                  <Badge tone={status.tone}>{status.label}</Badge>
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      <ImportTemplateDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}
