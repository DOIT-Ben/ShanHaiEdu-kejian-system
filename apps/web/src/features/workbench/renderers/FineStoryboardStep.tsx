import { ArrowRight, Check, Clock3, Image, RefreshCw, Volume2 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
import { SelectableCard } from "@/shared/ui/SelectableCard";
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
  const navigate = useNavigate();
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
  const videoStudioUrl = `/app/creation/videos?projectId=${encodeURIComponent(projectId)}&lessonId=${encodeURIComponent(lessonId)}&package=video-shots&itemId=shot-1`;
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
        title: "选择关键帧参考",
      });
    }
  };
  const confirmCurrentAndContinue = () => {
    if (approved) {
      void navigate(videoStudioUrl);
      return;
    }
    const nextAdopted = [...new Set([...(saved?.adoptedShots ?? []), shot.id])];
    const nextShotIndex = shots.findIndex((item) => !nextAdopted.includes(item.id));
    updateStoryboard({
      adoptedShots: nextAdopted,
      selectedShot: nextShotIndex >= 0 ? nextShotIndex : selected,
    });
  };
  const continueToNextShot = () => {
    const nextShotIndex = shots.findIndex((item) => !saved?.adoptedShots?.includes(item.id));
    if (nextShotIndex >= 0) updateStoryboard({ selectedShot: nextShotIndex }, false);
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
                  title: "选择关键帧参考",
                });
                void navigate(videoStudioUrl);
              }}
              size="md"
            >
              打开视频创作台
              <ArrowRight aria-hidden="true" />
            </Button>
          ) : adopted && !approved ? (
            <Button onClick={continueToNextShot} size="md">
              选择下一个镜头
              <ArrowRight aria-hidden="true" />
            </Button>
          ) : (
            <Button disabled={!canAdopt} onClick={confirmCurrentAndContinue} size="md">
              {approved ? "打开视频创作台" : canAdopt ? "确认当前关键帧" : "关键帧尚未准备好"}
              {approved ? <ArrowRight aria-hidden="true" /> : <Check aria-hidden="true" />}
            </Button>
          )
        }
        eyebrow="当前要做：选择关键帧参考"
        hideEyebrow
        status={
          <StatusBadge status={stale ? "stale" : approved ? "approved" : effectiveShotStatus} />
        }
        title={`${demo ? demoVideoTitle : topic} · 已选择 ${String(saved?.adoptedShots?.length ?? 0)}/${String(shots.length)} 个关键帧`}
      />
      {stale ? <StaleContentNotice reason={nodeState.stale_reason?.summary} /> : null}
      <div className="mt-4 grid gap-4 lg:grid-cols-[180px_minmax(0,1fr)_240px]">
        <aside className="space-y-2">
          {shots.map((item, index) => (
            <SelectableCard
              className="w-full p-3"
              key={item.id}
              onClick={() => {
                updateStoryboard({ selectedShot: index }, false);
                setMessage("");
              }}
              selected={selected === index}
              selectedLabel="当前镜头"
            >
              <div className="flex items-center gap-2 pr-20">
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
            </SelectableCard>
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
              <SelectableCard
                aria-label={`关键帧参考 ${String(candidate)}`}
                className="w-32 shrink-0 p-2"
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
                selected={selectedCandidate === candidate}
              >
                <VideoScenePreview
                  compact
                  topic={demo ? undefined : topic}
                  variant={demo ? selected + candidate - 1 : previewVariant + candidate - 1}
                />
                <span className="mt-1 block text-xs font-semibold">关键帧参考 {candidate}</span>
              </SelectableCard>
            ))}
          </div>
        </section>
        <aside className="h-fit rounded-[var(--sh-radius-md)] border border-[var(--sh-line-subtle)] bg-[var(--sh-surface-elevated)] p-4">
          <h2 className="font-semibold text-[var(--sh-ink-strong)]">关键帧说明</h2>
          <div className="mt-4 space-y-4 text-sm">
            <div>
              <p className="flex items-center gap-1.5 text-xs font-semibold text-[var(--sh-ink-muted)]">
                <Image aria-hidden="true" className="size-3.5" />
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
              当前仅为关键帧示意，视频与旁白尚未生成
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
              setMessage(`${shot.id} 的关键帧示意已更新，其他镜头保持不变。`);
            }}
            variant="secondary"
          >
            <RefreshCw aria-hidden="true" />
            只重做这个关键帧
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
