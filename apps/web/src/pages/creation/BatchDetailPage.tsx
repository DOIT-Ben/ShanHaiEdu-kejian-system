import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, Play, Sparkles } from "lucide-react";
import { useBatch, useBatchResults, useGenerateBatch, useUpdateBatchItem } from "@/features/creation";
import { SaveToProjectDialog } from "@/features/save-to-project";
import { CandidateGallery } from "@/features/workbench";
import type { CreationBatchItem } from "@/shared/api";
import { Badge, Button, Skeleton, Spinner, Textarea, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";

const ITEM_STATUS_META: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "warning" | "danger" }> = {
  draft: { label: "待填写", tone: "neutral" },
  ready: { label: "待生成", tone: "brand" },
  queued: { label: "排队中", tone: "running" },
  running: { label: "生成中", tone: "running" },
  review_required: { label: "等待你挑选", tone: "warning" },
  adopted: { label: "已采用", tone: "success" },
  saved: { label: "已保存", tone: "success" },
  failed: { label: "失败", tone: "danger" },
};

/**
 * 本次创作（批次）工作台（03 §3）：来自项目的待生成内容批量制作。
 * 左侧批次清单 + 中央当前项；保存回项目指定位置。
 */
export default function BatchDetailPage() {
  const { batchId = "" } = useParams();
  const { data, isPending } = useBatch(batchId);
  const generate = useGenerateBatch(batchId);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [saving, setSaving] = useState<{ resultId: string; item: CreationBatchItem } | null>(null);

  const batch = data?.batch ?? null;

  useEffect(() => {
    if (batch && !activeKey) {
      const firstActionable =
        batch.items.find((i) => i.status === "review_required" || i.status === "failed") ??
        batch.items.find((i) => i.status !== "saved") ??
        batch.items[0];
      if (firstActionable) setActiveKey(firstActionable.item_key);
    }
  }, [batch, activeKey]);

  if (isPending || !batch) {
    return (
      <div className="mx-auto flex w-full max-w-[var(--sh-content-max)] gap-6 px-6 py-8">
        <Skeleton className="h-96 w-64 rounded-lg" />
        <Skeleton className="h-96 flex-1 rounded-lg" />
      </div>
    );
  }

  const active = batch.items.find((i) => i.item_key === activeKey) ?? batch.items[0] ?? null;
  const pendingIds = batch.items
    .filter((i) => i.status === "ready" || i.status === "failed")
    .map((i) => i.id);
  const savedCount = batch.items.filter((i) => i.status === "saved").length;

  return (
    <div className="mx-auto w-full max-w-[var(--sh-content-max)] px-6 py-8">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link to="/app/creation">
            <ArrowLeft className="size-4" aria-hidden />
            创作中心
          </Link>
        </Button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-ink-strong">{batch.title}</h1>
        <span className="text-sm text-ink-muted">
          {savedCount}/{batch.items.length} 已保存
          {batch.source_project_title ? ` · 保存到「${batch.source_project_title}」` : ""}
        </span>
        {pendingIds.length > 0 ? (
          <Button
            className="ml-auto"
            loading={generate.isPending}
            loadingText="正在开始…"
            onClick={() =>
              generate.mutate(
                { itemIds: pendingIds },
                {
                  onSuccess: () => toast({ tone: "info", title: `开始生成 ${pendingIds.length} 项` }),
                  onError: (error) => toast({ tone: "danger", title: "无法生成", description: error.message }),
                },
              )
            }
          >
            <Play className="size-4" aria-hidden />
            生成全部待生成项（{pendingIds.length}）
          </Button>
        ) : null}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[260px_1fr]">
        <nav aria-label="本次创作清单" className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible">
          {batch.items.map((item) => {
            const meta = ITEM_STATUS_META[item.status] ?? { label: item.status, tone: "neutral" as const };
            return (
              <button
                key={item.item_key}
                type="button"
                onClick={() => setActiveKey(item.item_key)}
                className={cn(
                  "flex shrink-0 items-center gap-3 rounded-md border p-3 text-left transition-colors duration-150",
                  item.item_key === active?.item_key
                    ? "border-brand-500 bg-brand-50/60"
                    : "border-line-subtle bg-surface hover:bg-surface-soft",
                )}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-ink-strong">{item.title}</span>
                  <Badge tone={meta.tone} className="mt-1">
                    {item.status === "running" || item.status === "queued" ? <Spinner className="size-3" /> : null}
                    {meta.label}
                  </Badge>
                </span>
              </button>
            );
          })}
        </nav>

        {active ? (
          <BatchItemWorkspace
            key={active.item_key}
            batchId={batch.id}
            etag={data?.etag ?? ""}
            item={active}
            mediaKind={batch.studio_type === "video" ? "video" : "image"}
            onSave={(resultId) => setSaving({ resultId, item: active })}
          />
        ) : null}
      </div>

      <SaveToProjectDialog
        open={Boolean(saving)}
        onOpenChange={(open) => !open && setSaving(null)}
        resultId={saving?.resultId ?? null}
        defaultProjectId={batch.source_project_id ?? null}
        defaultSlotKey={saving?.item.target_slot_key ?? batch.default_save_target ?? "library.image"}
        slotLabel={saving?.item.title ?? "创作结果"}
        lockTarget={Boolean(saving?.item.target_slot_key)}
      />
    </div>
  );
}

function BatchItemWorkspace({
  batchId,
  etag,
  item,
  mediaKind,
  onSave,
}: {
  batchId: string;
  etag: string;
  item: CreationBatchItem;
  mediaKind: "image" | "video";
  onSave: (resultId: string) => void;
}) {
  const update = useUpdateBatchItem(batchId);
  const generate = useGenerateBatch(batchId);
  const { data: results } = useBatchResults(batchId, item.item_key);
  const prompt = (item.prompt ?? {}) as { description?: string };
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? prompt.description ?? "";
  const busy = item.status === "queued" || item.status === "running";

  const runGenerate = () => {
    const persistAndRun = () =>
      generate.mutate(
        { itemIds: [item.id] },
        {
          onSuccess: () => toast({ tone: "info", title: `「${item.title}」开始生成` }),
          onError: (error) => toast({ tone: "danger", title: "无法生成", description: error.message }),
        },
      );
    if (draft !== null && draft !== prompt.description) {
      update.mutate(
        { itemKey: item.item_key, etag, patch: { prompt: { ...prompt, description: draft } } },
        {
          onSuccess: persistAndRun,
          onError: (error) => toast({ tone: "danger", title: "保存要求失败", description: error.message }),
        },
      );
    } else {
      persistAndRun();
    }
  };

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-ink-strong">{item.title}</h2>
        {item.consistency_key ? <Badge tone="neutral">保持画面一致</Badge> : null}
        <span className="ml-auto">
          <Button
            size="sm"
            variant={results?.length ? "outline" : "primary"}
            loading={busy || generate.isPending || update.isPending}
            loadingText="正在生成…"
            onClick={runGenerate}
            disabled={!value.trim()}
          >
            <Sparkles className="size-4" aria-hidden />
            {results?.length ? "再生成一批" : "开始生成"}
          </Button>
        </span>
      </div>

      {item.reference_assets && item.reference_assets.length > 0 ? (
        <div className="rounded-md bg-surface-soft p-3">
          <p className="text-xs font-medium text-ink-muted">参考画面</p>
          <ul className="mt-2 flex gap-2 overflow-x-auto">
            {item.reference_assets.map((ref, index) => (
              <li key={index} className="shrink-0">
                {ref.preview_url ? (
                  <img src={ref.preview_url} alt={ref.role} className="h-16 w-24 rounded-md object-cover" />
                ) : (
                  <span className="flex h-16 w-24 items-center justify-center rounded-md border border-dashed border-line text-xs text-ink-faint">
                    {ref.role}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="rounded-lg border border-line-subtle bg-surface p-4">
        <label htmlFor={`prompt-${item.item_key}`} className="text-xs font-medium text-ink-muted">
          生成要求（完整指令，可修改）
        </label>
        <Textarea
          id={`prompt-${item.item_key}`}
          rows={3}
          value={value}
          className="mt-1.5"
          onChange={(e) => setDraft(e.target.value)}
        />
      </div>

      <CandidateGallery
        results={(results ?? []).filter((r) => r.review_state !== "discarded")}
        mediaKind={mediaKind}
        emptyHint={busy ? "正在生成候选…" : "点击「开始生成」制作候选。"}
        renderActions={(result) =>
          item.status === "saved" && result.id === item.adopted_result_id ? (
            <Button size="sm" variant="secondary" disabled>
              已保存到项目
            </Button>
          ) : (
            <Button size="sm" onClick={() => onSave(result.id)}>
              采用并保存
            </Button>
          )
        }
      />
    </div>
  );
}
