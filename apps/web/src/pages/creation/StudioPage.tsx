import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { Sparkles } from "lucide-react";
import { useBatch, useBatchResults, useCreateBatch, useGenerateBatch, useUpdateBatchItem } from "@/features/creation";
import { SaveToProjectDialog } from "@/features/save-to-project";
import { CandidateGallery } from "@/features/workbench";
import { Button, FormField, PageHeader, Skeleton, Textarea, toast } from "@/shared/ui";

const STUDIO_COPY = {
  image: {
    title: "制作图片",
    hint: "想要什么画面？说清楚内容、场景和用途。",
    placeholder: "例如：三年级数学课用的分数示意图，一个披萨平均分成 4 份，其中 3 份高亮，卡通风格，画面干净。",
    action: "开始生成",
    slotLabel: "教学图片",
    defaultSlot: "library.image",
  },
  video: {
    title: "制作视频",
    hint: "描述画面怎样变化、镜头持续多久；有参考画面可以先生成图片。",
    placeholder: "例如：一只卡通小狐狸把披萨切成四份，镜头从整块披萨慢慢拉近到其中三份，画面明亮温暖，持续 10 秒。",
    action: "开始生成",
    slotLabel: "视频片段",
    defaultSlot: "library.video",
  },
  presentation: {
    title: "制作 PPT 页面",
    hint: "说明这一页要讲什么、给谁看；正文页保持纯白底色。",
    placeholder: "例如：一页讲解「几分之几」的练习页，出示两道看图写分数的题目，题目区域大、字号大。",
    action: "开始生成",
    slotLabel: "PPT 页面",
    defaultSlot: "library.ppt_page",
  },
} as const;

export type StudioType = keyof typeof STUDIO_COPY;

/**
 * 独立单项创作台（03 §2）：没有左侧批次栏；
 * 主操作状态链：开始生成 → 采用这个结果 → 保存到项目 → 已保存。
 */
export default function StudioPage({ studioType }: { studioType: StudioType }) {
  const copy = STUDIO_COPY[studioType];
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const batchId = searchParams.get("batch");
  const create = useCreateBatch();
  const { data } = useBatch(batchId);
  const [description, setDescription] = useState("");
  const [savingResultId, setSavingResultId] = useState<string | null>(null);

  // 进入创作台即静默建立一次创作（草稿），刷新可通过 URL 恢复
  useEffect(() => {
    if (!batchId && !create.isPending) {
      create.mutate(
        { studioType, title: `${copy.title} ${new Date().toLocaleDateString("zh-CN")}` },
        {
          onSuccess: (batch) => setSearchParams({ batch: batch.id }, { replace: true }),
          onError: (error) => toast({ tone: "danger", title: "无法进入创作台", description: error.message }),
        },
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  const batch = data?.batch ?? null;
  const item = batch?.items[0] ?? null;

  useEffect(() => {
    if (item && description === "") {
      const existing = (item.prompt as { description?: string } | undefined)?.description;
      if (existing) setDescription(existing);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [item?.id]);

  if (!batch || !item) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4 px-6 py-8">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-64 rounded-lg" />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-8">
      <PageHeader title={copy.title} description={copy.hint} />
      <div className="mt-6 space-y-5">
        <StudioComposer
          key={item.id}
          batchId={batch.id}
          etag={data?.etag ?? ""}
          itemKey={item.item_key}
          itemId={item.id}
          itemStatus={item.status}
          description={description}
          onDescriptionChange={setDescription}
          placeholder={copy.placeholder}
          actionLabel={copy.action}
        />
        <StudioResults
          batchId={batch.id}
          itemKey={item.item_key}
          adoptedResultId={item.adopted_result_id ?? null}
          savedBindingId={item.saved_binding_id ?? null}
          mediaKind={studioType === "video" ? "video" : "image"}
          onSave={(resultId) => setSavingResultId(resultId)}
        />
      </div>
      <SaveToProjectDialog
        open={Boolean(savingResultId)}
        onOpenChange={(open) => !open && setSavingResultId(null)}
        resultId={savingResultId}
        defaultProjectId={batch.source_project_id ?? null}
        defaultSlotKey={item.target_slot_key ?? copy.defaultSlot}
        slotLabel={copy.slotLabel}
        onSaved={() => void navigate(`/app/creation/batches/${batch.id}`)}
      />
    </div>
  );
}

function StudioComposer({
  batchId,
  etag,
  itemKey,
  itemId,
  itemStatus,
  description,
  onDescriptionChange,
  placeholder,
  actionLabel,
}: {
  batchId: string;
  etag: string;
  itemKey: string;
  itemId: string;
  itemStatus: string;
  description: string;
  onDescriptionChange: (value: string) => void;
  placeholder: string;
  actionLabel: string;
}) {
  const update = useUpdateBatchItem(batchId);
  const generate = useGenerateBatch(batchId);
  const busy = itemStatus === "queued" || itemStatus === "running";

  const startGeneration = () => {
    if (!description.trim()) {
      toast({ tone: "warning", title: "先描述想要的内容" });
      return;
    }
    update.mutate(
      { itemKey, etag, patch: { prompt: { description: description.trim() } } },
      {
        onSuccess: () =>
          generate.mutate(
            { itemIds: [itemId] },
            {
              onSuccess: () => toast({ tone: "info", title: "开始生成", description: "完成后候选会出现在下方。" }),
              onError: (error) => toast({ tone: "danger", title: "无法生成", description: error.message }),
            },
          ),
        onError: (error) => toast({ tone: "danger", title: "保存要求失败", description: error.message }),
      },
    );
  };

  return (
    <section className="rounded-lg border border-line-subtle bg-surface p-5 shadow-card">
      <FormField label="生成要求（完整指令，可随时修改）">
        {({ id }) => (
          <Textarea
            id={id}
            rows={4}
            value={description}
            placeholder={placeholder}
            onChange={(e) => onDescriptionChange(e.target.value)}
          />
        )}
      </FormField>
      <div className="mt-4 flex items-center justify-end">
        <Button
          onClick={startGeneration}
          loading={update.isPending || generate.isPending || busy}
          loadingText={busy ? "正在生成…" : "正在开始…"}
          disabled={!description.trim()}
        >
          <Sparkles className="size-4" aria-hidden />
          {actionLabel}
        </Button>
      </div>
    </section>
  );
}

function StudioResults({
  batchId,
  itemKey,
  adoptedResultId,
  savedBindingId,
  mediaKind,
  onSave,
}: {
  batchId: string;
  itemKey: string;
  adoptedResultId: string | null;
  savedBindingId: string | null;
  mediaKind: "image" | "video";
  onSave: (resultId: string) => void;
}) {
  const { data: results } = useBatchResults(batchId, itemKey);
  const visible = (results ?? []).filter((r) => r.review_state !== "discarded");
  if (visible.length === 0) return null;

  return (
    <section aria-label="候选结果">
      <CandidateGallery
        results={visible}
        mediaKind={mediaKind}
        renderActions={(result) =>
          savedBindingId && result.id === adoptedResultId ? (
            <Button size="sm" variant="secondary" disabled>
              已保存到项目
            </Button>
          ) : (
            <Button size="sm" onClick={() => onSave(result.id)}>
              {result.id === adoptedResultId ? "再次保存" : "采用并保存到项目"}
            </Button>
          )
        }
      />
    </section>
  );
}
