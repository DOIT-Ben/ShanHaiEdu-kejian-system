import { useEffect, useState } from "react";
import { Link } from "react-router";
import { Lock, RefreshCcw } from "lucide-react";
import { validatePageCanvas, PPT_PAGE_TYPE_LABELS, TEXT_ROLE_LABELS } from "@/entities/content";
import { usePptPage, usePptPages, useRegeneratePptPage, useSavePptPage, usePptStyleContract } from "@/features/ppt";
import { AppError } from "@/shared/api";
import { pageDisplayName } from "@/shared/lib/teacherLanguage";
import { Badge, Button, Skeleton, Textarea, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { useStepNodeRun, useWorkbench } from "../context";
import { StepScaffold } from "../parts";

/**
 * 制作正文：封面门禁（无画面风格 → 引导回封面）；
 * 正文页一律纯白底色；文字直接可编辑；每页可重新生成。
 */
export function PptBodyCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun } = useStepNodeRun();
  const { data: pages, isPending } = usePptPages(lessonId);
  const { data: styleContract, isPending: styleLoading } = usePptStyleContract(lessonId);
  const [activePageId, setActivePageId] = useState<string | null>(null);

  useEffect(() => {
    if (!activePageId && pages && pages.length > 0) {
      const firstBody = pages.find((p) => p.page_type !== "cover") ?? pages[0];
      setActivePageId(firstBody.page_id);
    }
  }, [pages, activePageId]);

  if (isPending || styleLoading) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  // 封面门禁
  if (!styleContract) {
    return (
      <StepScaffold title="制作正文" status={nodeRun?.status}>
        <div className="mx-auto flex max-w-md flex-col items-center gap-4 rounded-lg border border-line-subtle bg-surface p-10 text-center shadow-card">
          <Lock className="size-8 text-ink-faint" aria-hidden />
          <div>
            <p className="text-base font-medium text-ink-strong">请先确定封面风格</p>
            <p className="mt-1 text-sm text-ink-muted">
              正文页面会沿用封面的画面风格，先去「设计封面」采用一张封面。
            </p>
          </div>
          <Button asChild>
            <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/ppt-cover`}>去设计封面</Link>
          </Button>
        </div>
      </StepScaffold>
    );
  }

  const activePage = pages?.find((p) => p.page_id === activePageId) ?? null;

  return (
    <StepScaffold
      title="制作正文"
      description={`画面风格：${styleContract.summary}`}
      status={nodeRun?.status}
    >
      <div className="grid gap-6 xl:grid-cols-[220px_1fr]">
        <nav aria-label="页面列表" className="flex gap-2 overflow-x-auto xl:flex-col xl:overflow-visible">
          {(pages ?? []).map((page, index) => (
            <button
              key={page.page_id}
              type="button"
              onClick={() => setActivePageId(page.page_id)}
              className={cn(
                "flex shrink-0 items-center gap-2.5 rounded-md border p-2.5 text-left transition-colors duration-150",
                page.page_id === activePageId
                  ? "border-brand-500 bg-brand-50/60"
                  : "border-line-subtle bg-surface hover:bg-surface-soft",
              )}
            >
              {page.preview_url ? (
                <img src={page.preview_url} alt="" className="h-12 w-20 shrink-0 rounded object-cover" />
              ) : (
                <span className="flex h-12 w-20 shrink-0 items-center justify-center rounded bg-surface-soft text-xs text-ink-faint">
                  待生成
                </span>
              )}
              <span className="min-w-0">
                <span className="block truncate text-xs font-medium text-ink-strong">
                  {page.page_type === "cover" ? "封面" : pageDisplayName(index + 1)}
                </span>
                <span className="mt-0.5 block truncate text-xs text-ink-muted">{page.teaching_task}</span>
              </span>
            </button>
          ))}
        </nav>
        {activePage ? (
          <PageEditor key={activePage.page_id} pageId={activePage.page_id} lessonId={lessonId} />
        ) : (
          <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
            左侧选择要编辑的页面。
          </p>
        )}
      </div>
    </StepScaffold>
  );
}

function PageEditor({ pageId, lessonId }: { pageId: string; lessonId: string }) {
  const { data, isPending } = usePptPage(pageId);
  const save = useSavePptPage(pageId, lessonId);
  const regenerate = useRegeneratePptPage(pageId, lessonId);
  const [draftBlocks, setDraftBlocks] = useState<Record<string, string> | null>(null);

  if (isPending || !data) {
    return <Skeleton className="h-96 rounded-lg" />;
  }

  const { detail } = data;
  const spec = detail.spec as Record<string, unknown> & {
    page_type?: string;
    visual?: { visual_decision?: string };
    editable_text_blocks?: { block_key: string; role: string; text: string }[];
  };
  const blocks = spec.editable_text_blocks ?? [];
  const isCover = spec.page_type === "cover";
  const busy = detail.page.status === "generating";

  const blockValue = (block: { block_key: string; text: string }) =>
    draftBlocks?.[block.block_key] ?? block.text;

  const dirty =
    draftBlocks !== null && blocks.some((block) => (draftBlocks[block.block_key] ?? block.text) !== block.text);

  const persist = () => {
    if (!dirty) return;
    const nextSpec = {
      ...spec,
      editable_text_blocks: blocks.map((block) => ({ ...block, text: blockValue(block) })),
    };
    const canvasError = validatePageCanvas(nextSpec as never);
    if (canvasError) {
      toast({ tone: "danger", title: "画布规则", description: canvasError });
      return;
    }
    save.mutate(
      { etag: data.etag ?? "", spec: nextSpec },
      {
        onSuccess: () => {
          setDraftBlocks(null);
          toast({ tone: "success", title: "页面已保存" });
        },
        onError: (error) => {
          const message =
            error instanceof AppError && error.code === "CANVAS_RULE_VIOLATION"
              ? "正文页必须保持纯白底色。"
              : error.message;
          toast({ tone: "danger", title: "保存失败", description: message });
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">{PPT_PAGE_TYPE_LABELS[spec.page_type ?? ""] ?? spec.page_type}</Badge>
        {spec.visual?.visual_decision ? (
          <Badge tone="neutral">
            {VISUAL_DECISION_LABELS[spec.visual.visual_decision] ?? spec.visual.visual_decision}
          </Badge>
        ) : null}
        {!isCover ? <span className="text-xs text-ink-faint">正文页 · 纯白底色（不可更改）</span> : null}
        <span className="ml-auto flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            loading={regenerate.isPending || busy}
            loadingText="正在生成…"
            onClick={() =>
              regenerate.mutate(undefined, {
                onSuccess: () => toast({ tone: "info", title: "正在重新生成本页" }),
                onError: (error) => {
                  const message =
                    error instanceof AppError && error.code === "COVER_NOT_APPROVED"
                      ? "请先确定封面风格，再制作正文页面。"
                      : error.message;
                  toast({ tone: "danger", title: "无法生成", description: message });
                },
              })
            }
          >
            <RefreshCcw className="size-4" aria-hidden />
            重新生成本页
          </Button>
          <Button size="sm" disabled={!dirty} loading={save.isPending} loadingText="保存中…" onClick={persist}>
            保存修改
          </Button>
        </span>
      </div>

      <div
        className={cn(
          "aspect-video w-full overflow-hidden rounded-lg border border-line-subtle shadow-card",
          isCover ? "bg-surface-soft" : "sh-paper-canvas",
        )}
      >
        {detail.page.preview_url ? (
          <img
            src={detail.page.preview_url}
            alt={`${detail.page.teaching_task} 预览`}
            className="size-full object-contain"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-sm text-ink-faint">
            本页还没有生成，点击「重新生成本页」。
          </div>
        )}
      </div>

      {blocks.length > 0 ? (
        <section aria-label="页面文字" className="rounded-lg border border-line-subtle bg-surface p-4">
          <p className="text-xs font-medium text-ink-muted">页面文字（改完点保存）</p>
          <div className="mt-3 space-y-3">
            {blocks.map((block) => (
              <div key={block.block_key}>
                <label htmlFor={`block-${block.block_key}`} className="text-xs text-ink-faint">
                  {TEXT_ROLE_LABELS[block.role as keyof typeof TEXT_ROLE_LABELS] ?? block.role}
                </label>
                <Textarea
                  id={`block-${block.block_key}`}
                  value={blockValue(block)}
                  rows={block.role === "title" ? 1 : 2}
                  className="mt-1"
                  onChange={(event) =>
                    setDraftBlocks((prev) => ({ ...(prev ?? {}), [block.block_key]: event.target.value }))
                  }
                />
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

/** 数学画面策略的教师文案（ppt-page-spec visual_decision）。 */
const VISUAL_DECISION_LABELS: Record<string, string> = {
  quantity_relation: "数量关系",
  whole_part: "整体与部分",
  comparison: "比较",
  transformation: "转化",
  unit_one: "单位一",
  change: "变化过程",
  operation: "运算过程",
  life_application: "生活应用",
  other: "其他",
};
