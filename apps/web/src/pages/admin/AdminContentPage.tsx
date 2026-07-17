import { useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Upload } from "lucide-react";
import { useContentPackages, useImportContentPackage } from "@/features/admin";
import { parseContentDefinition } from "@/entities/content";
import { formatDateTime } from "@/shared/lib/format";
import type { StatusTone } from "@/shared/lib/status";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
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

export const PACKAGE_STATUS_META: Record<string, { label: string; tone: StatusTone }> = {
  draft: { label: "草稿", tone: "neutral" },
  checking: { label: "系统检查中", tone: "running" },
  check_failed: { label: "检查未通过", tone: "danger" },
  dry_run: { label: "试运行中", tone: "warning" },
  published: { label: "已发布", tone: "success" },
};

export const DOMAIN_LABELS: Record<string, string> = {
  lesson_plan: "教案规范",
  intro_options: "导入方案规范",
  ppt: "PPT 规范",
  video: "视频规范",
  quality: "质量检查",
  style: "风格规范",
  prompt: "提示词规范",
};

/** 内容中心（04 §2.2）：上传 → 系统检查 → 预览变化 → 试运行 → 发布。 */
export default function AdminContentPage() {
  const { data: packages, isPending } = useContentPackages();
  const [importOpen, setImportOpen] = useState(false);

  return (
    <div>
      <PageHeader
        title="内容中心"
        description="内容规范决定教案等作品的结构。版本不可变：发布新版本，不修改旧版本。"
        actions={
          <Button onClick={() => setImportOpen(true)}>
            <Upload className="size-4" aria-hidden />
            上传内容包
          </Button>
        }
      />
      {isPending ? (
        <div className="mt-6 space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-16 rounded-lg" />
          ))}
        </div>
      ) : (
        <ul className="mt-6 space-y-3">
          {(packages ?? []).map((pkg) => {
            const meta = PACKAGE_STATUS_META[pkg.status] ?? { label: pkg.status, tone: "neutral" as StatusTone };
            return (
              <li key={pkg.id}>
                <Link
                  to={`/admin/content/${pkg.id}`}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-line-subtle bg-surface px-5 py-4 shadow-card transition-colors duration-150 hover:bg-surface-soft"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-ink-strong">{pkg.title}</span>
                    <span className="mt-0.5 block text-xs text-ink-muted">
                      {DOMAIN_LABELS[pkg.domain] ?? pkg.domain} · 第 {pkg.current_version_no} 版 ·{" "}
                      {formatDateTime(pkg.updated_at)}
                    </span>
                  </span>
                  <Badge tone={meta.tone}>{meta.label}</Badge>
                  <ArrowRight className="size-4 shrink-0 text-ink-faint" aria-hidden />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </div>
  );
}

function ImportDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const importPackage = useImportContentPackage();
  const [title, setTitle] = useState("");
  const [domain, setDomain] = useState("lesson_plan");
  const [definitionText, setDefinitionText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  const submit = () => {
    let definition: unknown;
    try {
      definition = parseContentDefinition(JSON.parse(definitionText));
      setParseError(null);
    } catch (error) {
      setParseError(error instanceof Error ? `内容定义不合法：${error.message.slice(0, 200)}` : "内容定义不合法。");
      return;
    }
    importPackage.mutate(
      { title: title.trim(), domain, definition },
      {
        onSuccess: () => {
          onOpenChange(false);
          setTitle("");
          setDefinitionText("");
          toast({ tone: "info", title: "已开始系统检查", description: "检查通过后可试运行并发布。" });
        },
        onError: (error) => toast({ tone: "danger", title: "上传失败", description: error.message }),
      },
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="上传内容包" description="粘贴内容定义 JSON。上传后先进行系统检查，不会直接生效。">
        <div className="space-y-4">
          <FormField label="名称" required>
            {({ id }) => (
              <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：小学数学教案 v3" />
            )}
          </FormField>
          <FormField label="所属领域" required>
            {({ id }) => (
              <Select value={domain} onValueChange={setDomain}>
                <SelectTrigger id={id}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(DOMAIN_LABELS).map(([key, label]) => (
                    <SelectItem key={key} value={key}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          </FormField>
          <FormField label="内容定义（JSON）" required error={parseError ?? undefined}>
            {({ id }) => (
              <Textarea
                id={id}
                rows={8}
                value={definitionText}
                onChange={(e) => setDefinitionText(e.target.value)}
                className="font-mono text-xs"
                placeholder='{"definition_key":"…","title":"…","fields":[…]}'
              />
            )}
          </FormField>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            disabled={!title.trim() || !definitionText.trim()}
            loading={importPackage.isPending}
            loadingText="正在上传…"
            onClick={submit}
          >
            上传并检查
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
