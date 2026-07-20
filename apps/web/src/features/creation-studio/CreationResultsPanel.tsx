import * as Dialog from "@radix-ui/react-dialog";
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Columns3,
  Download,
  Expand,
  LoaderCircle,
  Maximize2,
  Minimize2,
  X,
} from "lucide-react";
import { useEffect, useRef, useState, type Ref } from "react";
import { CreationResultCanvas } from "@/features/creation-studio/CreationResultCanvas";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import type { CreationStage, StudioType } from "@/features/creation-studio/model";
import { Button } from "@/shared/ui/Button";
import { IconButton } from "@/shared/ui/IconButton";

type CreationResultsPanelProps = {
  candidate: number;
  candidateCount: number;
  generation: number;
  hasUnappliedChanges: boolean;
  ratio: string;
  savedTarget?: string;
  stage: CreationStage;
  type: StudioType;
  onAdvance: () => void;
  onCandidateChange: (candidate: number) => void;
  onDownload: () => void;
  saveTriggerRef?: Ref<HTMLButtonElement>;
};
type PreviewContext = Pick<
  CreationResultsPanelProps,
  "candidate" | "generation" | "ratio" | "type"
>;
type EnlargedPreviewProps = PreviewContext & {
  onOpenChange: (open: boolean) => void;
  open: boolean;
};
type ComparisonDialogProps = PreviewContext & {
  candidates: number[];
  displayLabel: string;
  onOpenChange: (open: boolean) => void;
  onSelect: (candidate: number) => void;
  open: boolean;
};
function EnlargedPreview({
  candidate,
  generation,
  onOpenChange,
  open,
  ratio,
  type,
}: EnlargedPreviewProps) {
  const previewWidth = type === "image" ? "w-[min(92vw,82vh,960px)]" : "w-[min(92vw,1280px)]";
  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)]" />
        <Dialog.Content className="fixed inset-3 z-50 flex flex-col overflow-hidden rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] shadow-[var(--sh-shadow-floating)] md:inset-6">
          <div className="flex shrink-0 items-center justify-between border-b border-[var(--sh-line-subtle)] px-4 py-2">
            <div>
              <Dialog.Title className="font-semibold text-[var(--sh-ink-strong)]">
                放大查看
              </Dialog.Title>
              <Dialog.Description className="text-xs text-[var(--sh-ink-muted)]">
                当前作品 {candidate + 1} · {ratio}
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton className="size-9" label="关闭放大查看">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div className="grid min-h-0 flex-1 place-items-center overflow-auto bg-[var(--sh-surface-soft)] p-4">
            <div className={previewWidth} data-testid="creation-enlarged-visual">
              <CreationResultCanvas
                candidate={candidate}
                generation={generation}
                ratio={ratio}
                running={false}
                type={type}
              />
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function ComparisonDialog({
  candidate,
  candidates,
  displayLabel,
  generation,
  onOpenChange,
  onSelect,
  open,
  ratio,
  type,
}: ComparisonDialogProps) {
  return (
    <Dialog.Root onOpenChange={onOpenChange} open={open}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[var(--sh-overlay-scrim)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[92dvh] w-[min(94vw,1180px)] -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-elevated)] p-4 shadow-[var(--sh-shadow-floating)] md:p-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-lg font-semibold text-[var(--sh-ink-strong)]">
                对比作品
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-[var(--sh-ink-muted)]">
                并排检查细节，点击一项切换为当前作品。
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <IconButton className="size-9" label="关闭作品对比">
                <X aria-hidden="true" />
              </IconButton>
            </Dialog.Close>
          </div>
          <div
            className={`mt-4 grid gap-3 ${candidates.length === 2 ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}
            data-testid="creation-comparison-grid"
          >
            {candidates.map((item) => (
              <button
                aria-label={`查看${displayLabel} ${String(item + 1)}`}
                aria-pressed={candidate === item}
                className={`min-w-0 rounded-[var(--sh-radius-md)] border bg-[var(--sh-surface-soft)] p-2 text-left transition-[border-color,box-shadow] focus-visible:outline-none focus-visible:shadow-[var(--sh-shadow-focus)] ${candidate === item ? "border-[var(--sh-brand-500)] ring-2 ring-[var(--sh-brand-100)]" : "border-[var(--sh-line-default)] hover:border-[var(--sh-brand-300)]"}`}
                key={item}
                onClick={() => {
                  onSelect(item);
                  onOpenChange(false);
                }}
                type="button"
              >
                <CreativeResultVisual ratio={ratio} type={type} variant={(item + generation) % 3} />
                <span className="mt-2 block text-sm font-semibold text-[var(--sh-ink-strong)]">
                  {displayLabel} {item + 1}
                  {candidate === item ? " · 当前" : ""}
                </span>
              </button>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function CreationResultsPanel({
  candidate,
  candidateCount,
  generation,
  hasUnappliedChanges,
  onAdvance,
  onCandidateChange,
  onDownload,
  ratio,
  saveTriggerRef,
  savedTarget,
  stage,
  type,
}: CreationResultsPanelProps) {
  const [compareOpen, setCompareOpen] = useState(false);
  const [enlargedOpen, setEnlargedOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const previewRef = useRef<HTMLDivElement>(null);
  const running = stage === "running";
  const renderedGeneration = running ? Math.max(0, generation - 1) : generation;
  const candidates = Array.from({ length: candidateCount }, (_, index) => index);
  const compareStart = Math.min(Math.max(candidate - 1, 0), Math.max(candidateCount - 3, 0));
  const compareCandidates = candidates.slice(compareStart, compareStart + 3);
  const visualWidth = fullscreen
    ? type === "image"
      ? "w-[min(88vmin,960px)]"
      : "w-[min(92vw,1280px)]"
    : type === "image"
      ? "w-[min(100%,360px)] md:w-[clamp(480px,56vw,720px)]"
      : "w-full max-w-[960px]";
  const workspaceWidth = type === "image" ? "max-w-[760px]" : "max-w-[1120px]";
  const downloadLabel =
    type === "image" ? "下载这张图片" : type === "video" ? "下载关键帧说明" : "下载课件预览";
  const itemLabel = type === "image" ? "张" : type === "video" ? "张关键帧" : "套";
  const resultLabel = type === "video" ? "关键帧" : "作品";
  const candidateAriaLabel = type === "video" ? "关键帧参考" : "备选作品";
  const candidateDisplayLabel = type === "video" ? "关键帧" : "作品";
  const currentLabel =
    type === "video" ? "当前关键帧" : type === "presentation" ? "当前课件" : "当前作品";
  const resultReadyLabel = type === "video" ? "已准备" : "已完成";
  useEffect(() => {
    const handleFullscreenChange = () =>
      setFullscreen(document.fullscreenElement === previewRef.current);
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);
  const changeCandidate = (nextCandidate: number) => {
    if (nextCandidate >= 0 && nextCandidate < candidateCount) onCandidateChange(nextCandidate);
  };
  const toggleFullscreen = async () => {
    if (document.fullscreenElement === previewRef.current) {
      await document.exitFullscreen();
      return;
    }
    if (typeof previewRef.current?.requestFullscreen !== "function") {
      setEnlargedOpen(true);
      return;
    }
    try {
      await previewRef.current.requestFullscreen();
    } catch {
      setEnlargedOpen(true);
    }
  };
  return (
    <section
      aria-busy={running}
      aria-label="创作结果"
      className={`mx-auto flex w-full ${workspaceWidth} flex-col justify-start`}
      data-generation={generation}
      data-testid="creation-output-region"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-1">
        <div className="flex items-center gap-2">
          <span
            className={`grid size-8 place-items-center rounded-full ${running ? "bg-[var(--sh-brand-50)] text-[var(--sh-brand-700)]" : "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]"}`}
          >
            {running ? (
              <LoaderCircle
                aria-hidden="true"
                className="size-4 animate-spin motion-reduce:animate-none"
              />
            ) : (
              <Check aria-hidden="true" className="size-4" />
            )}
          </span>
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
            {running
              ? "正在创作新作品"
              : generation > 1
                ? `第 ${String(generation)} 轮${resultLabel}${resultReadyLabel}`
                : `本轮${resultLabel}${resultReadyLabel}`}
          </p>
        </div>
        <span className="text-xs font-medium text-[var(--sh-ink-muted)]">
          {running
            ? `正在生成 ${String(candidateCount)} ${itemLabel}`
            : type === "video"
              ? `${String(candidateCount)} 张关键帧`
              : `${String(candidateCount)} 个作品`}
        </span>
      </div>
      <div
        className={
          fullscreen
            ? "flex h-screen w-screen flex-col justify-center overflow-auto bg-[var(--sh-surface-elevated)] p-6"
            : "rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] p-2.5 shadow-[var(--sh-shadow-card)]"
        }
        data-testid="creation-preview-panel"
        ref={previewRef}
      >
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2 px-1">
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
            {currentLabel} {String(candidate + 1)} / {String(candidateCount)}
          </p>
          <div aria-label="预览工具" className="flex flex-wrap items-center justify-end gap-1">
            <IconButton
              className="size-9"
              disabled={running || candidate === 0}
              label={`上一张${candidateDisplayLabel}`}
              onClick={() => changeCandidate(candidate - 1)}
            >
              <ChevronLeft aria-hidden="true" />
            </IconButton>
            <IconButton
              className="size-9"
              disabled={running || candidate >= candidateCount - 1}
              label={`下一张${candidateDisplayLabel}`}
              onClick={() => changeCandidate(candidate + 1)}
            >
              <ChevronRight aria-hidden="true" />
            </IconButton>
            <span className="px-2 text-xs font-medium text-[var(--sh-ink-muted)]">{ratio}</span>
            <IconButton
              className="size-9"
              disabled={running}
              label="放大查看"
              onClick={() => setEnlargedOpen(true)}
            >
              <Expand aria-hidden="true" />
            </IconButton>
            <IconButton
              className="size-9"
              disabled={running}
              label={fullscreen ? "退出全屏" : "全屏查看"}
              onClick={() => void toggleFullscreen()}
            >
              {fullscreen ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}
            </IconButton>
            <Button
              disabled={running || candidateCount < 2}
              onClick={() => setCompareOpen(true)}
              size="sm"
              variant="quiet"
            >
              <Columns3 aria-hidden="true" />
              对比作品
            </Button>
          </div>
        </div>
        <div
          className={`mx-auto ${visualWidth}`}
          data-creation-type={type}
          data-render-generation={renderedGeneration}
          data-testid="creation-main-visual"
        >
          <CreationResultCanvas
            candidate={candidate}
            generation={renderedGeneration}
            ratio={ratio}
            running={running}
            type={type}
          />
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div aria-label={candidateAriaLabel} className="flex min-w-0 gap-2 overflow-x-auto pb-1">
          {candidates.map((item) => (
            <button
              aria-label={`${candidateAriaLabel} ${String(item + 1)}`}
              aria-pressed={candidate === item}
              className={`w-[76px] shrink-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1 text-left transition-[border-color,box-shadow] disabled:cursor-wait disabled:opacity-55 ${candidate === item ? "border-[var(--sh-brand-500)] ring-2 ring-[var(--sh-brand-100)]" : "border-[var(--sh-line-default)]"}`}
              disabled={running}
              key={item}
              onClick={() => changeCandidate(item)}
              type="button"
            >
              <CreativeResultVisual
                loading="lazy"
                ratio={ratio}
                type={type}
                variant={(item + renderedGeneration) % 3}
              />
              <span className="mt-1 block text-center text-[11px] font-semibold text-[var(--sh-ink-strong)]">
                {candidateDisplayLabel} {item + 1}
              </span>
            </button>
          ))}
        </div>
        <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
          <Button disabled={running} onClick={onDownload} variant="quiet">
            <Download aria-hidden="true" />
            {downloadLabel}
          </Button>
          {stage === "ready" || stage === "adopted" ? (
            <Button
              disabled={hasUnappliedChanges}
              onClick={onAdvance}
              ref={saveTriggerRef}
              title={hasUnappliedChanges ? "请先按新要求再创作一组" : undefined}
            >
              {stage === "ready" ? "就用这张" : "保存到项目"}
            </Button>
          ) : null}
        </div>
      </div>
      {stage === "saved" ? (
        <p className="mt-2 rounded-[var(--sh-radius-sm)] bg-[var(--sh-success-soft)] px-3 py-1.5 text-sm font-semibold text-[var(--sh-ink-strong)]">
          已放进“{savedTarget ?? "目标项目"}”，可在项目的素材与成果中查看。
        </p>
      ) : null}
      <EnlargedPreview
        candidate={candidate}
        generation={renderedGeneration}
        onOpenChange={setEnlargedOpen}
        open={enlargedOpen}
        ratio={ratio}
        type={type}
      />
      <ComparisonDialog
        candidate={candidate}
        candidates={compareCandidates}
        displayLabel={candidateDisplayLabel}
        generation={renderedGeneration}
        onOpenChange={setCompareOpen}
        onSelect={changeCandidate}
        open={compareOpen}
        ratio={ratio}
        type={type}
      />
    </section>
  );
}
