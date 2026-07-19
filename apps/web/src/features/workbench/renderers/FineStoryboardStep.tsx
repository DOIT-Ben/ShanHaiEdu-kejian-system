import {
  ArrowRight,
  Check,
  Clock3,
  Image,
  PencilLine,
  Play,
  RefreshCw,
  Volume2,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { VideoScenePreview } from "@/features/home/components/VideoScenePreview";
import { StaleContentNotice } from "@/features/workbench/components/StaleContentNotice";
import { WorkbenchPageFrame } from "@/features/workbench/components/WorkbenchPageFrame";
import {
  createTopicVideoShots,
  demoVideoShots,
  demoVideoTitle,
} from "@/features/workbench/lib/videoContent";
import {
  createShotsFromApprovedStory,
  getApprovedVideoAssets,
  getApprovedVideoStyle,
} from "@/features/workbench/lib/videoWorkflow";
import { markFineStoryboardDependentsStale } from "@/features/workbench/lib/invalidateDependents";
import { saveMockDraft, updateMockNodeState, useMockRuntime } from "@/shared/api/mocks/runtime";
import { Button } from "@/shared/ui/Button";
import { FocusPageHeader } from "@/shared/ui/FocusPageHeader";
import { StatusBadge } from "@/shared/ui/StatusBadge";
import { requiredItem } from "@/shared/lib/requiredItem";
import { demoProjectId } from "@/shared/data/mockData";

function approvedStoryboardContent(value: {
  adoptedShots?: string[];
  candidateByShot?: Record<string, number>;
}) {
  return {
    adoptedShots: value.adoptedShots ?? [],
    candidateByShot: value.candidateByShot ?? {},
  };
}

export function FineStoryboardStep() {
  const { lessonId = "", projectId = "" } = useParams();
  const runtime = useMockRuntime();
  const project = runtime.projects.find((item) => item.id === projectId);
  const demo = projectId === demoProjectId || !project;
  const topic = project?.knowledge_point ?? "本课知识点";
  const approvedStoryShots = createShotsFromApprovedStory(runtime, projectId, lessonId);
  const shots = demo ? demoVideoShots : (approvedStoryShots ?? createTopicVideoShots(topic));
  const approvedStyle = getApprovedVideoStyle(runtime, projectId, lessonId)?.selectedId;
  const previewVariant = approvedStyle === "clay" ? 1 : approvedStyle === "clean" ? 2 : 0;
  const approvedAssetCount = Object.keys(
    getApprovedVideoAssets(runtime, projectId, lessonId)?.resultIds ?? {},
  ).length;
  const draftKey = `project:${projectId}:lesson:${lessonId}:fine-storyboard`;
  const approvedKey = `${draftKey}:approved`;
  const nodeState = runtime.nodeStates[`${projectId}:${lessonId}:fine-storyboard`];
  const approved = nodeState?.status === "approved";
  const stale = nodeState?.status === "stale";
  type SavedStoryboard =
    | {
        adoptedShots?: string[];
        candidateByShot?: Record<string, number>;
        preparedShots?: string[];
        retryCounts?: Record<string, number>;
        selectedShot?: number;
      }
    | undefined;
  const currentSaved = runtime.drafts[draftKey]?.value as SavedStoryboard;
  const approvedSaved = runtime.drafts[approvedKey]?.value as SavedStoryboard;
  const saved = approved ? approvedSaved : (currentSaved ?? approvedSaved);
  const selected = saved?.selectedShot ?? 1;
  const shot = shots[selected] ?? requiredItem(shots, 0, "默认镜头");
  const effectiveShotStatus = saved?.preparedShots?.includes(shot.id)
    ? "review_required"
    : shot.status;
  const adopted = saved?.adoptedShots?.includes(shot.id) ?? false;
  const allAdopted = shots.every((item) => saved?.adoptedShots?.includes(item.id));
  const canAdopt = ["approved", "ready", "review_required"].includes(effectiveShotStatus);
  const selectedCandidate = saved?.candidateByShot?.[shot.id] ?? 1;
  const [message, setMessage] = useState("");
  const updateStoryboard = (
    patch: Partial<NonNullable<typeof saved>>,
    reevaluateApproval = true,
  ) => {
    const next = {
      adoptedShots: saved?.adoptedShots ?? [],
      candidateByShot: saved?.candidateByShot ?? {},
      preparedShots: saved?.preparedShots ?? [],
      retryCounts: saved?.retryCounts ?? {},
      selectedShot: selected,
      ...patch,
    };
    if (reevaluateApproval && nodeState?.status === "approved" && !approvedSaved && saved) {
      saveMockDraft(approvedKey, saved, {
        lessonId,
        nodeKey: "fine-storyboard",
        projectId,
      });
    }
    saveMockDraft(draftKey, next, { lessonId, nodeKey: "fine-storyboard", projectId });
    if (reevaluateApproval) {
      const nextApproved = shots.every((item) => next.adoptedShots.includes(item.id));
      if (
        nextApproved &&
        approvedSaved &&
        JSON.stringify(approvedStoryboardContent(approvedSaved)) !==
          JSON.stringify(approvedStoryboardContent(next))
      ) {
        markFineStoryboardDependentsStale(runtime, projectId, lessonId);
      }
      if (nextApproved) {
        saveMockDraft(approvedKey, next, {
          lessonId,
          nodeKey: "fine-storyboard",
          projectId,
        });
      }
      updateMockNodeState(projectId, lessonId, "fine-storyboard", {
        stale_reason: null,
        status: nextApproved ? "approved" : "review_required",
        title: "制作视频片段",
      });
    }
  };
  return (
    <WorkbenchPageFrame width="wide">
      <FocusPageHeader
        action={
          stale && allAdopted ? (
            <Button
              onClick={() => {
                updateMockNodeState(projectId, lessonId, "fine-storyboard", {
                  stale_reason: null,
                  status: "approved",
                  title: "制作视频片段",
                });
              }}
              size="md"
            >
              <Check aria-hidden="true" />
              重新确认全部片段
            </Button>
          ) : approved ? (
            <>
              <Button
                onClick={() =>
                  updateStoryboard({
                    adoptedShots: (saved?.adoptedShots ?? []).filter((id) => id !== shot.id),
                  })
                }
                size="md"
                variant="secondary"
              >
                <PencilLine aria-hidden="true" />
                重新选择当前片段
              </Button>
              <Button asChild size="md">
                <Link to={`/app/projects/${projectId}/lessons/${lessonId}/work/final-video`}>
                  合成完整视频
                  <ArrowRight aria-hidden="true" />
                </Link>
              </Button>
            </>
          ) : adopted ? (
            <Button
              onClick={() =>
                updateStoryboard({
                  adoptedShots: (saved?.adoptedShots ?? []).filter((id) => id !== shot.id),
                })
              }
              size="md"
              variant="secondary"
            >
              <PencilLine aria-hidden="true" />
              重新选择片段
            </Button>
          ) : (
            <Button
              disabled={!canAdopt}
              onClick={() =>
                updateStoryboard({
                  adoptedShots: [...new Set([...(saved?.adoptedShots ?? []), shot.id])],
                })
              }
              size="md"
            >
              <Check aria-hidden="true" />
              {canAdopt ? "采用这个结果" : "片段尚未准备好"}
            </Button>
          )
        }
        eyebrow="当前要做：检查并采用视频片段"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : effectiveShotStatus} />
        }
        title={`${demo ? demoVideoTitle : topic} · 已采用 ${String(saved?.adoptedShots?.length ?? 0)}/${String(shots.length)} 个片段`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)_240px]">
        <aside className="space-y-2">
          {shots.map((item, index) => (
            <button
              aria-pressed={selected === index}
              className={`w-full rounded-[var(--sh-radius-sm)] border p-3 text-left ${selected === index ? "border-[var(--sh-brand-500)] bg-[var(--sh-brand-50)]" : "border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)]"}`}
              key={item.id}
              onClick={() => {
                updateStoryboard({ selectedShot: index }, false);
                setMessage("");
              }}
              type="button"
            >
              <div className="flex items-center justify-between gap-2">
                <strong className="text-sm text-[var(--sh-ink-strong)]">{item.id}</strong>
                <StatusBadge
                  status={
                    saved?.adoptedShots?.includes(item.id)
                      ? "approved"
                      : saved?.preparedShots?.includes(item.id)
                        ? "review_required"
                        : item.status
                  }
                />
              </div>
              <p className="mt-2 line-clamp-2 text-xs text-[var(--sh-ink-muted)]">{item.beat}</p>
            </button>
          ))}
        </aside>
        <section className="min-w-0">
          <div className="rounded-[var(--sh-radius-md)] bg-[var(--sh-surface-player)] p-3">
            <VideoScenePreview
              topic={demo ? undefined : topic}
              variant={demo ? selected : previewVariant}
            />
          </div>
          <div className="mt-3 flex gap-2 overflow-x-auto">
            {[1, 2, 3].map((candidate) => (
              <button
                aria-label={`备选片段 ${String(candidate)}`}
                aria-pressed={selectedCandidate === candidate}
                className={`w-32 shrink-0 rounded-[var(--sh-radius-sm)] border bg-[var(--sh-surface-elevated)] p-2 text-left ${selectedCandidate === candidate ? "border-[var(--sh-brand-500)]" : "border-[var(--sh-line-subtle)]"}`}
                key={candidate}
                onClick={() =>
                  updateStoryboard({
                    adoptedShots: (saved?.adoptedShots ?? []).filter((id) => id !== shot.id),
                    candidateByShot: {
                      ...(saved?.candidateByShot ?? {}),
                      [shot.id]: candidate,
                    },
                  })
                }
                type="button"
              >
                <VideoScenePreview
                  compact
                  topic={demo ? undefined : topic}
                  variant={demo ? selected + candidate - 1 : previewVariant + candidate - 1}
                />
                <span className="mt-1 block text-xs font-semibold">备选片段 {candidate}</span>
              </button>
            ))}
          </div>
        </section>
        <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">镜头内容</h2>
          <div className="mt-4 space-y-4 text-sm">
            <div>
              <p className="flex items-center gap-1.5 text-xs font-semibold text-[var(--sh-ink-muted)]">
                <Play aria-hidden="true" className="size-3.5" />
                主要画面
              </p>
              <textarea
                aria-label="主要画面"
                className="mt-1 min-h-24 w-full resize-y rounded-[var(--sh-radius-sm)] border border-transparent bg-[var(--sh-surface-soft)] p-2 outline-none focus:border-[var(--sh-brand-500)]"
                value={shot.beat}
                readOnly
              />
            </div>
            <p className="flex items-start gap-2">
              <Clock3 aria-hidden="true" className="mt-0.5 size-4 text-[var(--sh-brand-600)]" />
              {shot.duration} 秒 · {shot.movement}
            </p>
            <p className="flex items-start gap-2">
              <Image aria-hidden="true" className="mt-0.5 size-4 text-[var(--sh-brand-600)]" />
              {String(approvedAssetCount || 2)} 张已批准参考画面
            </p>
            <p className="flex items-start gap-2">
              <Volume2 aria-hidden="true" className="mt-0.5 size-4 text-[var(--sh-brand-600)]" />
              旁白稍后独立制作
            </p>
          </div>
          <Button
            className="mt-5 w-full"
            onClick={() => {
              updateStoryboard({
                adoptedShots: (saved?.adoptedShots ?? []).filter((id) => id !== shot.id),
                retryCounts: {
                  ...(saved?.retryCounts ?? {}),
                  [shot.id]: (saved?.retryCounts?.[shot.id] ?? 0) + 1,
                },
                preparedShots: [...new Set([...(saved?.preparedShots ?? []), shot.id])],
              });
              setMessage(`${shot.id} 已重新制作完成，其他镜头保持不变。`);
            }}
            variant="secondary"
          >
            <RefreshCw aria-hidden="true" />
            只重做这个镜头
          </Button>
          {message ? (
            <p className="mt-3 text-xs font-medium text-[var(--sh-success)]" role="status">
              {message}
            </p>
          ) : null}
        </aside>
      </div>
    </WorkbenchPageFrame>
  );
}
