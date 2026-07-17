import { useState } from "react";
import { CheckCircle2, Star } from "lucide-react";
import { INTRO_CATEGORY_LABELS } from "@/shared/lib/teacherLanguage";
import { sortByRecommendation } from "@/entities/content";
import { useCurrentIntroSelection, useIntroOptions, useSelectIntro } from "@/features/intro";
import { AppError } from "@/shared/api";
import { Badge, Button, ConfirmDialog, Skeleton, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { useStepNodeRun, useWorkbench } from "../context";
import { StepScaffold } from "../parts";

/**
 * 选择一套方案：唯一决定视频依据的一步（两阶段隔离：
 * 视频只依赖选中方案快照，绝不携带教案正文）。
 */
export function IntroSelectionCanvas() {
  const { lessonId } = useWorkbench();
  const { nodeRun } = useStepNodeRun();
  const { data, isPending } = useIntroOptions(lessonId);
  const { data: selection } = useCurrentIntroSelection(lessonId);
  const select = useSelectIntro(lessonId);
  const [confirming, setConfirming] = useState<string | null>(null);

  if (isPending || !data) {
    return (
      <div className="grid gap-4 p-6 md:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <Skeleton key={i} className="h-40 rounded-lg" />
        ))}
      </div>
    );
  }

  const { optionSet } = data;
  const sorted = sortByRecommendation(optionSet.options);
  const recommendedKey = sorted[0]?.option_key;
  const selectedKey = selection?.option_key ?? null;
  const confirmingOption = optionSet.options.find((o) => o.option_key === confirming) ?? null;

  return (
    <StepScaffold
      title="选择一套导入方案"
      description="选中的方案将作为课堂导入和导入视频的唯一依据。选择后可以更换，但会影响已生成的视频。"
      status={nodeRun?.status}
    >
      {selectedKey ? (
        <p className="mb-5 flex items-center gap-2 rounded-lg border border-success-200 bg-success-50 p-3.5 text-sm text-ink">
          <CheckCircle2 className="size-4 shrink-0 text-success" aria-hidden />
          已选择「{optionSet.options.find((o) => o.option_key === selectedKey)?.title ?? selectedKey}」。
          导入视频将基于这套方案制作。
        </p>
      ) : null}
      <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {sorted.map((option) => {
          const isSelected = option.option_key === selectedKey;
          return (
            <li key={option.option_key}>
              <article
                className={cn(
                  "flex h-full flex-col rounded-lg border bg-surface p-4 shadow-card transition-colors duration-150",
                  isSelected ? "border-brand-500 ring-1 ring-brand-500" : "border-line-subtle",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs text-ink-faint">{INTRO_CATEGORY_LABELS[option.category]}</p>
                    <h3 className="mt-0.5 text-sm font-semibold text-ink-strong">{option.title}</h3>
                  </div>
                  <span className="flex shrink-0 items-center gap-1">
                    {option.option_key === recommendedKey ? (
                      <Badge tone="brand" icon={<Star className="size-3" aria-hidden />}>
                        推荐
                      </Badge>
                    ) : null}
                    {isSelected ? <Badge tone="success">已选择</Badge> : null}
                  </span>
                </div>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-ink">{option.hook}</p>
                <p className="mt-2 text-xs text-ink-muted">
                  约 {option.duration_seconds} 秒 · 交给课堂：{option.handoff_moment}
                </p>
                <div className="mt-3 border-t border-line-subtle pt-3">
                  <Button
                    className="w-full"
                    variant={isSelected ? "outline" : "primary"}
                    disabled={isSelected}
                    onClick={() => setConfirming(option.option_key)}
                  >
                    {isSelected ? "当前使用" : selectedKey ? "改用这套" : "就用这套"}
                  </Button>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
      <ConfirmDialog
        open={Boolean(confirming)}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={`确定使用「${confirmingOption?.title ?? ""}」？`}
        description={
          selectedKey
            ? "更换方案后，之前基于旧方案生成的视频内容会标记为「内容已变化」。"
            : "选择后，导入视频将围绕这套方案制作。"
        }
        confirmLabel="确定使用"
        loading={select.isPending}
        onConfirm={() => {
          if (!confirming) return;
          select.mutate(
            { optionKey: confirming, optionSetVersionId: optionSet.option_set_id },
            {
              onSuccess: () => {
                setConfirming(null);
                toast({
                  tone: "success",
                  title: "方案已确定",
                  description: "可以开始制作导入视频了。",
                });
              },
              onError: (error) => {
                setConfirming(null);
                const message =
                  error instanceof AppError && error.code === "OPTION_SET_STALE"
                    ? "九套方案已更新，请刷新页面后重新选择。"
                    : error.message;
                toast({ tone: "danger", title: "选择失败", description: message });
              },
            },
          );
        }}
      />
    </StepScaffold>
  );
}
