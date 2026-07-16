import { useMemo, useState } from "react";
import { useOutletContext } from "react-router";
import { BookOpen, PencilLine } from "lucide-react";
import type { ProjectOutletContext } from "@/layouts/project-layout";
import { parseContent, textbookEvidenceContentSchema, type EvidencePage } from "@/entities/content";
import { useSubmitEvidenceCorrections, useTextbookEvidence } from "@/features/projects";
import { useUploadSource } from "@/features/uploads";
import { useProjectTasks } from "@/features/tasks";
import { cn } from "@/shared/lib/cn";
import { AppError } from "@/shared/api";
import {
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogFooter,
  EmptyState,
  FormField,
  PageHeader,
  Progress,
  Skeleton,
  Textarea,
  toast,
} from "@/shared/ui";
import { AppErrorPanel, UploadDropzone } from "@/widgets";

function CorrectionDialog({
  open,
  onOpenChange,
  page,
  projectId,
  rowVersion,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  page: EvidencePage | null;
  projectId: string;
  rowVersion: number;
}) {
  const submit = useSubmitEvidenceCorrections(projectId);
  const [value, setValue] = useState("");
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next && page) setValue(page.ocr_text);
        onOpenChange(next);
      }}
    >
      <DialogContent title={`校正第 ${page?.page_number} 页识别文本`} description="校正结果会生成新的证据版本，供课时划分引用。">
        <FormField label="识别文本" required>
          {({ id, describedBy }) => (
            <Textarea
              id={id}
              aria-describedby={describedBy}
              rows={8}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              className="font-mono text-xs leading-5"
            />
          )}
        </FormField>
        {submit.isError ? <AppErrorPanel error={submit.error} title="校正提交失败" /> : null}
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            loading={submit.isPending}
            disabled={!page || value.trim().length === 0}
            onClick={() => {
              if (!page) return;
              submit.mutate(
                {
                  corrections: [{ page_number: page.page_number, field: "ocr_text", corrected_value: value }],
                  row_version: rowVersion,
                },
                {
                  onSuccess: () => {
                    toast({ tone: "success", title: "校正已提交", description: "已生成新的证据版本。" });
                    onOpenChange(false);
                  },
                },
              );
            }}
          >
            提交校正
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 教材页：上传 → 解析进度 → 证据浏览与校正。 */
export function TextbookPage() {
  const { project } = useOutletContext<ProjectOutletContext>();
  const projectId = project.project_id;
  const evidence = useTextbookEvidence(projectId);
  const upload = useUploadSource(projectId);
  const tasks = useProjectTasks(projectId, {}, { refetchInterval: 3000 });
  const [activePage, setActivePage] = useState(0);
  const [correctionFor, setCorrectionFor] = useState<EvidencePage | null>(null);

  const content = useMemo(
    () => parseContent(textbookEvidenceContentSchema, evidence.data?.content),
    [evidence.data],
  );

  const parseTask = (tasks.data ?? []).find(
    (task) => task.task_type === "textbook_parse" && ["queued", "running", "waiting_provider", "downloading"].includes(task.status),
  );
  const failedParse = (tasks.data ?? []).find((task) => task.task_type === "textbook_parse" && task.status === "failed");

  const noEvidence = evidence.isError && evidence.error instanceof AppError && evidence.error.status === 404;

  return (
    <div className="space-y-4 p-6">
      <PageHeader title="教材" description="上传教材 PDF，系统解析为分页证据；证据支持人工校正，供课时划分与教案生成引用。" />

      {parseTask ? (
        <div className="rounded-panel border border-line bg-surface-1 px-5 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-medium text-ink-1">正在解析教材…</p>
            <span className="text-sm tabular-nums text-ink-2">{Math.round(parseTask.progress_percent)}%</span>
          </div>
          <Progress className="mt-2" value={parseTask.progress_percent} />
          <p className="mt-1.5 text-xs text-ink-muted">{parseTask.progress_message ?? "解析完成后证据会显示在下方。"}</p>
        </div>
      ) : null}

      {failedParse && !content ? (
        <AppErrorPanel
          error={new AppError({ code: failedParse.error?.code ?? "PARSE_FAILED", message: failedParse.error?.message ?? "教材解析失败。", status: 500, retryable: true, traceId: failedParse.error?.trace_id })}
          title="教材解析失败"
          extraActions={
            <UploadDropzoneInline projectId={projectId} uploading={upload.isPending} onFile={(file) => upload.mutate({ file, sourceType: "textbook" })} />
          }
        />
      ) : null}

      {evidence.isPending && !noEvidence ? (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      ) : content ? (
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <nav className="max-h-[70vh] overflow-y-auto rounded-panel border border-line bg-surface-1 p-2" aria-label="教材页码">
            {content.pages.map((page, index) => (
              <button
                key={page.page_number}
                type="button"
                onClick={() => setActivePage(index)}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-control px-3 py-2 text-left text-sm transition-colors",
                  index === activePage ? "bg-brand-selected text-brand" : "text-ink-2 hover:bg-surface-hover",
                )}
              >
                <span className="truncate">
                  P{page.page_number} {page.title ?? ""}
                </span>
                {page.low_confidence ? <Badge tone="warning">低置信</Badge> : null}
              </button>
            ))}
          </nav>
          <section className="rounded-panel border border-line bg-surface-1 p-5">
            {content.pages[activePage] ? (
              <>
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold text-ink-1">
                    第 {content.pages[activePage].page_number} 页
                    {content.pages[activePage].title ? ` · ${content.pages[activePage].title}` : ""}
                  </h3>
                  <Button size="sm" variant="secondary" onClick={() => setCorrectionFor(content.pages[activePage])}>
                    <PencilLine className="size-3.5" aria-hidden />
                    校正本页
                  </Button>
                </div>
                {content.pages[activePage].low_confidence ? (
                  <p className="mt-2 rounded-control bg-warning-surface px-3 py-2 text-xs text-warning">
                    本页识别置信度较低，请核对关键数字与公式后再用于教案生成。
                  </p>
                ) : null}
                <div className="mt-3 space-y-2">
                  {content.pages[activePage].blocks.map((block, index) => (
                    <p
                      key={index}
                      className={cn(
                        "rounded-control px-3 py-2 text-sm leading-6",
                        block.type === "heading"
                          ? "bg-surface-2 font-semibold text-ink-1"
                          : block.type === "example"
                            ? "border border-brand/30 bg-brand-selected text-ink-1"
                            : block.type === "exercise"
                              ? "border border-line text-ink-2"
                              : "text-ink-2",
                      )}
                    >
                      {block.type === "example" ? "【例题】" : block.type === "exercise" ? "【练习】" : block.type === "figure" ? "【图】" : ""}
                      {block.text}
                    </p>
                  ))}
                </div>
              </>
            ) : null}
          </section>
        </div>
      ) : noEvidence && !parseTask && !failedParse ? (
        <div className="mx-auto max-w-xl">
          <UploadDropzone
            accept=".pdf"
            uploading={upload.isPending}
            onFile={(file) =>
              upload.mutate(
                { file, sourceType: "textbook" },
                { onSuccess: () => toast({ tone: "success", title: "上传成功", description: "教材解析已开始，完成后自动展示证据。" }) },
              )
            }
          />
          {upload.isError ? <AppErrorPanel className="mt-3" error={upload.error} title="教材上传失败" /> : null}
        </div>
      ) : evidence.isError && !noEvidence ? (
        <AppErrorPanel error={evidence.error} title="教材证据加载失败" onRetry={() => void evidence.refetch()} />
      ) : !content && evidence.data ? (
        <EmptyState icon={<BookOpen className="size-8" aria-hidden />} title="证据内容格式异常" description="请重新上传教材或联系管理员。" />
      ) : null}

      <CorrectionDialog
        open={correctionFor !== null}
        onOpenChange={(open) => {
          if (!open) setCorrectionFor(null);
        }}
        page={correctionFor}
        projectId={projectId}
        rowVersion={evidence.data?.row_version ?? 1}
      />
    </div>
  );
}

function UploadDropzoneInline({
  projectId: _projectId,
  uploading,
  onFile,
}: {
  projectId: string;
  uploading?: boolean;
  onFile: (file: File) => void;
}) {
  return (
    <label className="inline-flex cursor-pointer">
      <input
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          event.target.value = "";
        }}
      />
      <span className="inline-flex h-8 items-center rounded-control bg-brand px-3 text-sm font-medium text-white hover:bg-brand-hover">
        {uploading ? "上传中…" : "重新上传教材"}
      </span>
    </label>
  );
}
