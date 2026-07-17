import { useEffect, useRef, useState, type DragEvent } from "react";
import { useParams } from "react-router";
import { CheckCircle2, FileText, FileUp, GripVertical, Plus, Trash2 } from "lucide-react";
import { useConfirmScope, useMaterial, useUploadMaterial } from "@/features/materials";
import {
  useApproveDivision,
  useDivision,
  useSaveDivision,
  type DivisionEntryDraft,
} from "@/features/lesson-division";
import { AppError } from "@/shared/api";
import {
  Button,
  EmptyState,
  Input,
  PageHeader,
  Panel,
  PanelBody,
  PanelHeader,
  Skeleton,
  Spinner,
  toast,
} from "@/shared/ui";

/** 教材与课时（02 §3）：上传解析 → 证据确认范围 → 课时划分编辑与批准。 */
export default function MaterialsPage() {
  const { projectId = "" } = useParams();
  const { data: material, isPending } = useMaterial(projectId);
  const upload = useUploadMaterial(projectId);
  const confirmScope = useConfirmScope(projectId);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <PageHeader
        title="当前要做：准备教材与课时"
        description="上传教材 → 确认识别范围 → 批准课时划分，之后进入课时创作。"
      />
      <div className="mt-8 space-y-6">
        {isPending ? (
          <Skeleton className="h-48 rounded-lg" />
        ) : !material ? (
          <UploadZone
            uploading={upload.isPending}
            onFile={(file) =>
              upload.mutate(file, {
                onError: (error) =>
                  toast({
                    tone: "danger",
                    title: "上传失败",
                    description: error instanceof AppError ? error.message : "请稍后重试。",
                  }),
              })
            }
          />
        ) : (
          <Panel>
            <PanelHeader
              title="教材"
              description={material.file_name}
              actions={
                material.status === "parsed" ? (
                  <Button
                    loading={confirmScope.isPending}
                    loadingText="正在确认…"
                    onClick={() =>
                      confirmScope.mutate(undefined, {
                        onSuccess: () =>
                          toast({
                            tone: "success",
                            title: "范围已确认",
                            description: "系统正在生成课时划分建议。",
                          }),
                        onError: (error) => toast({ tone: "danger", title: "确认失败", description: error.message }),
                      })
                    }
                  >
                    确认范围，生成课时划分
                  </Button>
                ) : material.status === "scope_confirmed" ? (
                  <span className="inline-flex items-center gap-1.5 text-sm font-medium text-success">
                    <CheckCircle2 className="size-4" aria-hidden />
                    范围已确认
                  </span>
                ) : null
              }
            />
            <PanelBody>
              {material.status === "uploading" || material.status === "scanning" || material.status === "parsing" ? (
                <div className="flex items-center gap-3 text-sm text-ink-muted">
                  <Spinner className="size-4" />
                  {material.status === "uploading"
                    ? "正在上传…"
                    : material.status === "scanning"
                      ? "正在安全检查…"
                      : "正在识别教材内容…"}
                </div>
              ) : material.status === "failed" ? (
                <p className="text-sm text-danger">{material.failure_reason ?? "教材解析失败，请重新上传。"}</p>
              ) : (
                <>
                  <p className="text-sm text-ink">
                    {material.knowledge_scope ?? "识别完成。"}
                    {material.page_count ? `（共 ${material.page_count} 页）` : ""}
                  </p>
                  {material.evidence && material.evidence.length > 0 ? (
                    <ul className="mt-4 grid gap-2 sm:grid-cols-2">
                      {material.evidence.map((item) => (
                        <li
                          key={item.page_no}
                          className="flex items-start gap-2.5 rounded-md border border-line-subtle bg-surface-soft p-3"
                        >
                          <FileText className="mt-0.5 size-4 shrink-0 text-brand-500" aria-hidden />
                          <span className="text-sm">
                            <span className="font-medium text-ink-strong">第 {item.page_no} 页</span>
                            <span className="mt-0.5 block text-ink-muted">{item.summary}</span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </>
              )}
            </PanelBody>
          </Panel>
        )}

        {material?.status === "scope_confirmed" ? <DivisionSection projectId={projectId} /> : null}
      </div>
    </div>
  );
}

function UploadZone({ onFile, uploading }: { onFile: (file: File) => void; uploading: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      className={`rounded-lg border-2 border-dashed p-12 text-center transition-colors duration-150 ${
        dragOver ? "border-brand-500 bg-brand-50/50" : "border-line bg-surface"
      }`}
    >
      <FileUp className="mx-auto size-10 text-ink-faint" aria-hidden />
      <p className="mt-4 text-base font-medium text-ink-strong">上传教材 PDF</p>
      <p className="mt-1 text-sm text-ink-muted">拖拽文件到这里，或点击选择文件。识别过程通常不到一分钟。</p>
      <Button
        className="mt-5"
        loading={uploading}
        loadingText="正在上传…"
        onClick={() => inputRef.current?.click()}
      >
        选择 PDF 文件
      </Button>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="sr-only"
        aria-label="选择教材 PDF"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
    </div>
  );
}

function DivisionSection({ projectId }: { projectId: string }) {
  const { data, isPending } = useDivision(projectId);
  const save = useSaveDivision(projectId);
  const approve = useApproveDivision(projectId);
  const [drafts, setDrafts] = useState<DivisionEntryDraft[] | null>(null);
  const division = data?.division;
  const approved = division?.status === "approved";

  useEffect(() => {
    // 服务端最新划分同步为编辑草稿（未在编辑时）
    if (division && drafts === null && division.entries.length > 0) {
      setDrafts(
        division.entries.map((entry) => ({
          entry_id: entry.entry_id,
          title: entry.title,
          focus: entry.focus,
          duration_minutes: entry.duration_minutes ?? 40,
        })),
      );
    }
  }, [division, drafts]);

  if (isPending || !division) {
    return <Skeleton className="h-48 rounded-lg" />;
  }
  if (division.status === "not_ready") {
    return (
      <Panel>
        <PanelBody className="flex items-center gap-3 text-sm text-ink-muted">
          <Spinner className="size-4" />
          正在依据教材证据生成课时划分建议…
        </PanelBody>
      </Panel>
    );
  }

  const entries = drafts ?? [];
  const updateEntry = (index: number, patch: Partial<DivisionEntryDraft>) => {
    setDrafts((prev) => (prev ? prev.map((e, i) => (i === index ? { ...e, ...patch } : e)) : prev));
  };

  const persist = (next: DivisionEntryDraft[], message?: string) => {
    if (!data) return;
    save.mutate(
      { etag: data.etag ?? "", entries: next },
      {
        onSuccess: () => {
          if (message) toast({ tone: "success", title: message });
        },
        onError: (error) => {
          if (error instanceof AppError && error.isEditConflict) {
            toast({ tone: "warning", title: "内容已变化", description: "课时划分已在其他位置更新，已为你刷新。" });
            setDrafts(null);
          } else {
            toast({ tone: "danger", title: "保存失败", description: error.message });
          }
        },
      },
    );
  };

  return (
    <Panel>
      <PanelHeader
        title="课时划分"
        description={
          approved
            ? "已批准。课时已创建，可进入课时工作台。"
            : (division.source_evidence_note ?? "请确认每个课时的主题与重点，可增删调整。")
        }
        actions={
          approved ? (
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-success">
              <CheckCircle2 className="size-4" aria-hidden />
              已批准
            </span>
          ) : (
            <Button
              loading={approve.isPending}
              loadingText="正在批准…"
              disabled={entries.length === 0 || save.isPending}
              onClick={() =>
                approve.mutate(undefined, {
                  onSuccess: () =>
                    toast({ tone: "success", title: "课时划分已批准", description: "课时已创建，可以开始写教案了。" }),
                  onError: (error) => toast({ tone: "danger", title: "批准失败", description: error.message }),
                })
              }
            >
              批准课时划分
            </Button>
          )
        }
      />
      <PanelBody className="space-y-3">
        {entries.map((entry, index) => (
          <div
            key={entry.entry_id ?? `new-${index}`}
            className="flex items-start gap-2 rounded-md border border-line-subtle bg-surface-soft p-3"
          >
            <GripVertical className="mt-2.5 size-4 shrink-0 text-ink-faint" aria-hidden />
            <span className="mt-2 w-6 shrink-0 text-center text-sm font-semibold text-brand-600">
              {index + 1}
            </span>
            <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-[1fr_1fr_96px]">
              <Input
                value={entry.title}
                aria-label={`课时 ${index + 1} 标题`}
                disabled={approved}
                onChange={(e) => updateEntry(index, { title: e.target.value })}
                onBlur={() => !approved && persist(entries)}
              />
              <Input
                value={entry.focus}
                aria-label={`课时 ${index + 1} 重点`}
                disabled={approved}
                onChange={(e) => updateEntry(index, { focus: e.target.value })}
                onBlur={() => !approved && persist(entries)}
              />
              <Input
                type="number"
                min={10}
                max={90}
                value={entry.duration_minutes}
                aria-label={`课时 ${index + 1} 时长（分钟）`}
                disabled={approved}
                onChange={(e) => updateEntry(index, { duration_minutes: Number(e.target.value) || 40 })}
                onBlur={() => !approved && persist(entries)}
              />
            </div>
            {!approved ? (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`删除课时 ${index + 1}`}
                disabled={entries.length <= 1}
                onClick={() => {
                  const next = entries.filter((_, i) => i !== index);
                  setDrafts(next);
                  persist(next);
                }}
              >
                <Trash2 className="size-4 text-ink-muted" aria-hidden />
              </Button>
            ) : null}
          </div>
        ))}
        {entries.length === 0 ? (
          <EmptyState title="暂无课时" description="点击下方按钮添加课时。" />
        ) : null}
        {!approved ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              const next = [
                ...entries,
                { entry_id: null, title: `新课时 ${entries.length + 1}`, focus: "", duration_minutes: 40 },
              ];
              setDrafts(next);
              persist(next);
            }}
          >
            <Plus className="size-4" aria-hidden />
            添加课时
          </Button>
        ) : null}
      </PanelBody>
    </Panel>
  );
}
