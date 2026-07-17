import { useState } from "react";
import { Film, RefreshCcw } from "lucide-react";
import { useGenerateShot, useShotResults, useVideoProject, useVideoShots } from "@/features/video";
import { useSaveToProject } from "@/features/save-to-project";
import { shotDisplayName } from "@/shared/lib/teacherLanguage";
import { Badge, Button, Skeleton, Spinner, toast } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { useStepNodeRun, useWorkbench } from "../context";
import { CandidateGallery, StepScaffold, StaleBanner } from "../parts";

const SHOT_STATUS_META: Record<string, { label: string; tone: "neutral" | "brand" | "running" | "success" | "warning" | "danger" }> = {
  draft: { label: "待完善", tone: "neutral" },
  ready: { label: "可生成", tone: "brand" },
  generating: { label: "正在生成", tone: "running" },
  review_required: { label: "等待你挑选", tone: "warning" },
  adopted: { label: "已采用", tone: "success" },
  failed: { label: "生成失败", tone: "danger" },
};

/**
 * 制作视频片段：逐镜头生成候选 → 挑选采用（采用时才产生 clip_id）。
 * 单镜头重试，不整链重来（VIDEO_PRODUCTION §7）。
 */
export function VideoClipsCanvas() {
  const { projectId, lessonId } = useWorkbench();
  const { nodeRun, isPending } = useStepNodeRun();
  const { data: videoProject } = useVideoProject(lessonId);
  const { data: shots, isPending: shotsLoading } = useVideoShots(videoProject?.id ?? null);
  const [activeShotId, setActiveShotId] = useState<string | null>(null);

  if (isPending || shotsLoading) {
    return <Skeleton className="m-6 h-96 rounded-lg" />;
  }

  const status = nodeRun?.status;

  if (!videoProject || !shots || shots.length === 0) {
    return (
      <StepScaffold title="制作视频片段" status={status}>
        <p className="rounded-lg border border-dashed border-line bg-surface-soft p-8 text-center text-sm text-ink-muted">
          {status === "disabled"
            ? "本课时未启用导入视频。"
            : "镜头清单还没有准备好，请先完成前面的视频步骤。"}
        </p>
      </StepScaffold>
    );
  }

  const active = shots.find((s) => s.id === activeShotId) ?? shots.find((s) => s.status !== "adopted") ?? shots[0];
  const adoptedCount = shots.filter((s) => s.status === "adopted").length;

  return (
    <StepScaffold
      title="制作视频片段"
      description={`逐个镜头生成并挑选片段（${adoptedCount}/${shots.length} 已采用）。全部采用后可合成完整视频。`}
      status={status}
    >
      {status === "stale" && nodeRun ? <StaleBanner nodeRun={nodeRun} /> : null}
      <div className="grid gap-6 xl:grid-cols-[240px_1fr]">
        <nav aria-label="镜头列表" className="flex gap-2 overflow-x-auto xl:flex-col xl:overflow-visible">
          {shots.map((shot) => {
            const meta = SHOT_STATUS_META[shot.status] ?? { label: shot.status, tone: "neutral" as const };
            return (
              <button
                key={shot.id}
                type="button"
                onClick={() => setActiveShotId(shot.id)}
                className={cn(
                  "flex shrink-0 items-center gap-3 rounded-md border p-3 text-left transition-colors duration-150",
                  shot.id === active?.id
                    ? "border-brand-500 bg-brand-50/60"
                    : "border-line-subtle bg-surface hover:bg-surface-soft",
                )}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-surface-soft text-xs font-semibold text-ink">
                  {shot.position}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium text-ink-strong">
                    {shotDisplayName(shot.position)}
                  </span>
                  <Badge tone={meta.tone} className="mt-1">
                    {shot.status === "generating" ? <Spinner className="size-3" /> : null}
                    {meta.label}
                  </Badge>
                </span>
              </button>
            );
          })}
        </nav>
        {active ? (
          <ShotWorkspace
            key={active.id}
            shot={active}
            videoProjectId={videoProject.id}
            nodeRunId={nodeRun?.id ?? null}
            projectId={projectId}
          />
        ) : null}
      </div>
    </StepScaffold>
  );
}

type ShotItem = NonNullable<ReturnType<typeof useVideoShots>["data"]>[number];

function ShotWorkspace({
  shot,
  videoProjectId,
  nodeRunId,
  projectId,
}: {
  shot: ShotItem;
  videoProjectId: string;
  nodeRunId: string | null;
  projectId: string;
}) {
  const generate = useGenerateShot(videoProjectId);
  const save = useSaveToProject();
  const { data: candidates } = useShotResults(nodeRunId, shot.shot_key);
  const spec = shot.shot;

  const runGenerate = () =>
    generate.mutate(shot.id, {
      onSuccess: () => toast({ tone: "info", title: `${shotDisplayName(shot.position)}开始生成` }),
      onError: (error) => toast({ tone: "danger", title: "无法生成", description: error.message }),
    });

  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-ink-strong">{shotDisplayName(shot.position)}</h2>
        <span className="text-xs text-ink-muted">镜头持续 {spec.duration_seconds ?? 10} 秒</span>
        <span className="ml-auto flex gap-2">
          <Button
            variant={shot.status === "failed" ? "primary" : "outline"}
            size="sm"
            loading={generate.isPending || shot.status === "generating"}
            loadingText="正在生成…"
            onClick={runGenerate}
          >
            <RefreshCcw className="size-4" aria-hidden />
            {shot.status === "failed" ? "重试本镜头" : candidates?.length ? "再生成一批" : "生成片段候选"}
          </Button>
        </span>
      </div>

      {shot.status === "failed" && shot.failure_reason ? (
        <p className="rounded-md border border-danger-200 bg-danger-50 p-3 text-sm text-danger-700" role="alert">
          {shot.failure_reason}（只需重试这个镜头，其他镜头不受影响）
        </p>
      ) : null}

      {spec.prompt_text ? (
        <div className="rounded-md bg-surface-soft p-3">
          <p className="text-xs font-medium text-ink-muted">画面怎样变化</p>
          <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-ink">{spec.prompt_text}</p>
        </div>
      ) : null}

      {shot.current_clip ? (
        <div className="flex items-center gap-3 rounded-lg border border-success-200 bg-success-50 p-4">
          <Film className="size-5 shrink-0 text-success" aria-hidden />
          <div className="min-w-0 flex-1 text-sm">
            <p className="font-medium text-ink-strong">已采用片段</p>
            <p className="mt-0.5 text-ink-muted">重新采用其他候选会替换它（旧片段保留在历史）。</p>
          </div>
          {shot.current_clip.preview_url ? (
            <img
              src={shot.current_clip.preview_url}
              alt="已采用片段预览"
              className="h-16 w-28 shrink-0 rounded-md object-cover"
            />
          ) : null}
        </div>
      ) : null}

      <CandidateGallery
        results={(candidates ?? []).filter((r) => r.review_state !== "discarded")}
        mediaKind="video"
        emptyHint={
          shot.status === "generating"
            ? "正在生成候选片段…"
            : "点击「生成片段候选」，系统会依据镜头图片生成多个候选。"
        }
        renderActions={(result) =>
          result.review_state === "adopted" ? (
            <Button size="sm" disabled variant="secondary">
              已采用
            </Button>
          ) : (
            <Button
              size="sm"
              loading={save.isPending}
              onClick={() =>
                save.mutate(
                  {
                    resultId: result.id,
                    projectId,
                    slotKey: `video.clip.${shot.shot_key}`,
                    replaceMode: "replace_active",
                  },
                  {
                    onSuccess: () =>
                      toast({
                        tone: "success",
                        title: "片段已采用",
                        description: `${shotDisplayName(shot.position)}的片段已确定。`,
                      }),
                    onError: (error) => toast({ tone: "danger", title: "采用失败", description: error.message }),
                  },
                )
              }
            >
              采用这个片段
            </Button>
          )
        }
      />
    </div>
  );
}
