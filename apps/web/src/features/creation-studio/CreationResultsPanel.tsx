import { Check, Download, LoaderCircle } from "lucide-react";
import type { Ref } from "react";
import { CreationResultCanvas } from "@/features/creation-studio/CreationResultCanvas";
import { CreativeResultVisual } from "@/features/creation-studio/CreativeResultVisual";
import type { CreationStage, StudioType } from "@/features/creation-studio/model";
import { Button } from "@/shared/ui/Button";

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
  const running = stage === "running";
  const renderedGeneration = running ? Math.max(0, generation - 1) : generation;
  const visualWidth =
    type === "image"
      ? "w-[clamp(168px,22vw,220px)]"
      : "w-full max-w-[min(600px,max(240px,calc((100dvh-520px)*1.7778)))]";
  const workspaceWidth = type === "image" ? "max-w-[720px]" : "max-w-[1040px]";
  const candidates = Array.from({ length: candidateCount }, (_, index) => index);
  const downloadLabel =
    type === "image" ? "下载这张图片" : type === "video" ? "下载关键帧说明" : "下载课件预览";
  const itemLabel = type === "image" ? "张" : type === "video" ? "张关键帧" : "套";
  const resultLabel = type === "video" ? "关键帧" : "作品";
  const candidateAriaLabel = type === "video" ? "关键帧参考" : "备选作品";
  const candidateDisplayLabel = type === "video" ? "关键帧" : "作品";
  const resultReadyLabel = type === "video" ? "已准备" : "已完成";
  const nextAction = running
    ? `正在准备 ${String(candidateCount)} ${itemLabel}，完成后会自动显示。`
    : hasUnappliedChanges
      ? "下方要求已有修改，重新创作后再选择作品。"
      : stage === "ready"
        ? "满意就选用；还想调整，就在下方修改要求。"
        : stage === "adopted"
          ? "作品已经选好，可以保存到项目继续使用。"
          : "作品已经保存，也可以继续在下方修改并创作新一组。";

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
            className={`grid size-8 place-items-center rounded-full ${running ? "bg-[var(--sh-warning-soft)] text-[var(--sh-warning)]" : "bg-[var(--sh-success-soft)] text-[var(--sh-success-strong)]"}`}
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
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
              {running
                ? "正在创作新作品"
                : generation > 1
                  ? `第 ${String(generation)} 轮${resultLabel}${resultReadyLabel}`
                  : `本轮${resultLabel}${resultReadyLabel}`}
            </p>
            <p className="text-xs text-[var(--sh-ink-muted)]">{nextAction}</p>
          </div>
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
        className="rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-soft)] p-2.5 shadow-[var(--sh-shadow-card)]"
        data-testid="creation-preview-panel"
      >
        <div className="mb-1.5 flex items-center justify-between gap-3 px-1">
          <p className="text-sm font-semibold text-[var(--sh-ink-strong)]">
            {type === "video" ? "当前关键帧" : "当前作品"} {String(candidate + 1)}
          </p>
          <span className="rounded-full border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] px-2.5 py-1 text-xs text-[var(--sh-ink-muted)]">
            {ratio}
          </span>
        </div>
        <div
          className={`mx-auto ${visualWidth}`}
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
        <div
          aria-label={type === "video" ? "关键帧参考" : "备选作品"}
          className="flex min-w-0 gap-2 overflow-x-auto pb-1"
        >
          {candidates.map((item) => (
            <button
              aria-label={`${candidateAriaLabel} ${String(item + 1)}`}
              aria-pressed={candidate === item}
              className={`w-[76px] shrink-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-1 text-left transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 disabled:translate-y-0 disabled:cursor-wait disabled:opacity-55 ${candidate === item ? "border-[var(--sh-brand-500)] ring-2 ring-[var(--sh-brand-100)]" : "border-[var(--sh-line-default)]"}`}
              disabled={running}
              key={item}
              onClick={() => onCandidateChange(item)}
              type="button"
            >
              <CreativeResultVisual
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
    </section>
  );
}
